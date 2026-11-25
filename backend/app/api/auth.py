"""Cuentas: sesión, registro, activación y recuperación de contraseña."""
from urllib.parse import urlsplit

from flask import current_app, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from app.api import api_bp
from app.extensions import db
from app.models import User
from app.services import auth_service
from app.utils.http import json_error, no_store
from app.utils.security import (client_ip, current_user, end_session, get_csrf_token, limiter,
                                rotate_csrf_token, start_session)
from app.utils.timeutils import utcnow
from app.utils.validation import Validator, valid_email

# Hash de relleno: el tiempo de respuesta es igual exista o no el correo
_DUMMY_HASH = generate_password_hash("ferrepro-dummy-password-never-valid")

INVALID_CREDENTIALS = "Correo o contraseña incorrectos."
CHECK_EMAIL = ("Si los datos son correctos, te enviamos un correo con los siguientes pasos. "
               "Revisa también la carpeta de spam.")
INVALID_LINK = "El enlace no es válido o ya venció. Solicita uno nuevo."


def _base_url():
    configured = current_app.config["PUBLIC_BASE_URL"]
    if current_app.testing or current_app.debug:
        return configured or request.host_url.rstrip("/")
    url = urlsplit(configured)
    local_http = url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1"}
    if (url.scheme == "https" or local_http) and url.hostname and not (url.username or url.password or url.query or url.fragment):
        return configured
    return None


def _mail_unavailable(message="No pudimos enviar el correo. Intenta nuevamente en unos minutos."):
    return json_error(503, "mail_unavailable", message)


def _payload():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _limited(*checks):
    """checks: pares (nombre_del_limite, clave). Devuelve una respuesta 429 o None."""
    worst = 0
    for name, key in checks:
        allowed, retry = limiter(name).hit(key)
        if not allowed:
            worst = max(worst, retry)
    if worst:
        return json_error(429, "rate_limited", "Demasiados intentos. Espera unos minutos y vuelve a intentarlo.",
                          retry_after=worst)
    return None


def _signed_in(user, status=200):
    csrf = start_session(user)
    user.last_login_at = utcnow()
    db.session.commit()
    return no_store(jsonify(user=user.to_session(), csrf=csrf), status)


@api_bp.get("/auth/csrf")
def csrf_token():
    return no_store(jsonify(csrf=get_csrf_token()))


@api_bp.get("/auth/me")
def me():
    user = current_user()
    return no_store(jsonify(user=user.to_session() if user else None, csrf=get_csrf_token()))


@api_bp.post("/auth/login")
def login():
    data = _payload()
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
        return json_error(400, "validation", "Escribe tu correo y tu contraseña.")
    email = email.strip().lower()
    if len(password) > 256 or not valid_email(email):
        return json_error(401, "invalid_credentials", INVALID_CREDENTIALS)

    ip = client_ip()
    blocked = _limited(("login_ip", ip), ("login", f"{ip}|{email}"))
    if blocked:
        return blocked

    user = User.by_email(email)
    if user is None:
        check_password_hash(_DUMMY_HASH, password)
        valid = False
    else:
        # Cuentas sin activar o desactivadas reciben el mismo mensaje generico
        valid = user.check_password(password) and user.is_active and not user.email_verification_pending
    if not valid:
        return json_error(401, "invalid_credentials", INVALID_CREDENTIALS)

    limiter("login").reset(f"{ip}|{email}")
    return _signed_in(user)


@api_bp.post("/auth/logout")
def logout():
    end_session()
    db.session.commit()
    return no_store(jsonify(ok=True, csrf=rotate_csrf_token()))


@api_bp.post("/auth/register")
def register():
    ip = client_ip()
    blocked = _limited(("register", ip))
    if blocked:
        return blocked

    data = _payload()
    v = Validator(data)
    name = v.text("name", 150, min_len=3)
    email = v.email("email")
    password = data.get("password")
    if not isinstance(password, str) or not password:
        v.error("password", "Este campo es obligatorio.")
    else:
        problem = auth_service.password_problem(password, email)
        if problem:
            v.error("password", problem)
    v.accepted("accept_terms", "Para crear tu cuenta debes aceptar los Términos y condiciones.")
    v.accepted("accept_privacy", "Para crear tu cuenta debes autorizar el tratamiento de tus datos personales.")
    v.raise_if_errors()

    base_url = _base_url()
    user = auth_service.register(name, email, password, ip)
    if user is None:
        message = "Este correo ya está registrado. Inicia sesión o solicita un enlace de activación."
        return json_error(409, "email_taken", message, fields={"email": message})
    if not base_url or not auth_service.send_activation(user, base_url):
        return _mail_unavailable("Tu cuenta quedó pendiente. Solicita otro enlace de activación.")
    return no_store(jsonify(ok=True, message="Revisa tu correo para activar tu cuenta."), 202)


@api_bp.post("/auth/activation/resend")
def resend_activation():
    v = Validator(_payload())
    email = v.email("email")
    v.raise_if_errors()
    blocked = _limited(("resend_ip", client_ip()), ("resend_email", email))
    if blocked:
        return blocked
    base_url = _base_url()
    if not base_url:
        return _mail_unavailable()
    user = User.by_email(email)
    if user is not None and auth_service.is_pending(user):
        if not auth_service.send_activation(user, base_url):
            return _mail_unavailable()
    return no_store(jsonify(ok=True, message=CHECK_EMAIL), 202)


@api_bp.post("/auth/activate")
def activate():
    blocked = _limited(("token", client_ip()))
    if blocked:
        return blocked
    token = (_payload()).get("token")
    user = auth_service.activate(token)
    if user is None:
        return json_error(400, "invalid_link", INVALID_LINK)
    return _signed_in(user)


@api_bp.post("/auth/password/forgot")
def forgot_password():
    ip = client_ip()
    v = Validator(_payload())
    email = v.email("email")
    v.raise_if_errors()
    blocked = _limited(("forgot_ip", ip), ("forgot_email", email))
    if blocked:
        return blocked
    base_url = _base_url()
    if not base_url:
        return _mail_unavailable()
    auth_service.request_password_reset(email, base_url)
    return no_store(jsonify(ok=True, message=CHECK_EMAIL), 202)


@api_bp.post("/auth/password/reset")
def reset_password():
    blocked = _limited(("token", client_ip()))
    if blocked:
        return blocked
    data = _payload()
    password = data.get("password")
    if not isinstance(password, str) or not password:
        return json_error(400, "validation", "Revisa los campos marcados.", fields={"password": "Este campo es obligatorio."})
    user, problem = auth_service.reset_password(data.get("token"), password)
    if user is None:
        return json_error(400, "invalid_link", INVALID_LINK)
    if problem:
        return json_error(400, "validation", "Revisa los campos marcados.", fields={"password": problem})
    return _signed_in(user)
