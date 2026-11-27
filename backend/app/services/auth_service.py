"""Registro, activación por correo y recuperación de contraseña."""
import hashlib
import re
import secrets

from flask import current_app
from sqlalchemy.exc import IntegrityError
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User, record_consent
from app.services.mailer import send_email
from app.utils.timeutils import utcnow

SALT_RESET = "ferrepro.password-reset.v1"
SALT_ACTIVATE = "ferrepro.account-activate.v1"

COMMON_PASSWORDS = {
    "contraseña123", "contrasena123", "password1234", "123456789abc", "abc123456789",
    "ferrepro2026", "ferreteria123", "qwerty123456", "colombia2026", "medellin2026",
}


def password_problem(password, email=None):
    if not isinstance(password, str) or len(password) < 12:
        return "Usa al menos 12 caracteres."
    if len(password) > 128:
        return "Usa como máximo 128 caracteres."
    if not re.search(r"[^\W\d_]", password) or not re.search(r"\d", password):
        return "Combina letras y números."
    if password.lower() in COMMON_PASSWORDS:
        return "Esa contraseña es muy común. Elige otra."
    local = (email or "").split("@")[0].lower()
    if len(local) >= 4 and local in password.lower():
        return "No uses tu correo dentro de la contraseña."
    return None


def is_pending(user):
    return not user.is_active and user.email_verification_pending


def can_use_links(user):
    """Activas o pendientes de activar; nunca las desactivadas por un administrador."""
    return user.is_active or is_pending(user)


def _stamp(user):
    raw = f"{user.password_hash}|{int(bool(user.is_active))}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _serializer(salt):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def make_token(user, salt):
    return _serializer(salt).dumps([user.id, _stamp(user)])


def read_token(token, salt, max_age):
    if not isinstance(token, str) or not 20 <= len(token) <= 300:
        return None
    try:
        user_id, stamp = _serializer(salt).loads(token, max_age=max_age)
        user = db.session.get(User, int(user_id), with_for_update=True, populate_existing=True)
    except (BadSignature, ValueError, TypeError):
        return None
    if user is None or not isinstance(stamp, str) or not secrets.compare_digest(_stamp(user), stamp):
        return None
    return user


# ---------------------------------------------------------------------------
# Correos
# ---------------------------------------------------------------------------

def _store_name():
    from app.models import StoreSetting
    return StoreSetting.get().store_name or "FerrePro"


def _hours(seconds):
    hours = seconds // 3600
    return f"{hours} horas" if hours >= 2 else f"{seconds // 60} minutos"


def send_activation(user, base_url):
    max_age = current_app.config["ACCOUNT_ACTIVATION_MAX_AGE"]
    link = f"{base_url}/#activar/{make_token(user, SALT_ACTIVATE)}"
    store = _store_name()
    return send_email(user.email, f"Confirma tu cuenta de {store}",
               f"Hola, {user.full_name}.\n\n"
               f"Para activar tu cuenta de {store}, abre este enlace:\n{link}\n\n"
               f"El enlace vence en {_hours(max_age)} y sirve una sola vez.\n"
               "Si no creaste esta cuenta, ignora este mensaje: no se activará.\n")


def send_password_reset(user, base_url):
    max_age = current_app.config["PASSWORD_RESET_MAX_AGE"]
    link = f"{base_url}/#restablecer/{make_token(user, SALT_RESET)}"
    store = _store_name()
    send_email(user.email, f"Restablece tu contraseña de {store}",
               f"Hola, {user.full_name}.\n\n"
               f"Recibimos una solicitud para cambiar la contraseña de tu cuenta de {store}.\n"
               f"Elige una nueva aquí:\n{link}\n\n"
               f"El enlace vence en {_hours(max_age)} y sirve una sola vez. "
               "Si no lo pediste, ignora este mensaje: tu contraseña no cambia.\n", background=True)


# ---------------------------------------------------------------------------
# Flujos
# ---------------------------------------------------------------------------

def register(full_name, email, password, ip_address, verified=False):
    """Crea la cuenta de cliente. verified=True la deja activa (sin confirmación de correo)."""
    if User.by_email(email) is not None:
        return None
    now = utcnow()
    user = User(email=email, full_name=full_name, role=User.ROLE_CUSTOMER, is_active=verified,
                email_verification_pending=not verified, password_hash=generate_password_hash(password), created_at=now)
    try:
        db.session.add(user)
        db.session.flush()
        record_consent("registration", "terms", accepted_at=now, user_id=user.id, ip_address=ip_address)
        record_consent("registration", "habeas_data", accepted_at=now, user_id=user.id, ip_address=ip_address)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if User.by_email(email) is not None:
            return None
        raise
    return user


def activate(token):
    user = read_token(token, SALT_ACTIVATE, current_app.config["ACCOUNT_ACTIVATION_MAX_AGE"])
    if user is None or not is_pending(user):
        return None
    user.is_active = True
    user.email_verification_pending = False
    return user


def request_password_reset(email, base_url):
    user = User.by_email(email)
    if user is not None and can_use_links(user):
        send_password_reset(user, base_url)


def reset_password(token, new_password):
    """Devuelve el usuario o None. Un problema de contrasena se devuelve como texto."""
    user = read_token(token, SALT_RESET, current_app.config["PASSWORD_RESET_MAX_AGE"])
    if user is None or not can_use_links(user):
        return None, None
    problem = password_problem(new_password, user.email)
    if problem:
        return user, problem
    user.set_password(new_password)
    if is_pending(user):
        user.is_active = True
        user.email_verification_pending = False
    return user, None
