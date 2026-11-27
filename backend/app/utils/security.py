import secrets
import threading
import time
from collections import deque
from functools import wraps
from urllib.parse import urlparse

from flask import abort, current_app, request, session

_USER_KEY = "ferrepro.current_user"  # cache por peticion (request.environ), nunca compartido

from app.extensions import db

CSRF_HEADER = "X-CSRF-Token"


# ---------------------------------------------------------------------------
# CSRF: token por sesion enviado en una cabecera propia (patron synchronizer token)
# ---------------------------------------------------------------------------

def get_csrf_token():
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


def rotate_csrf_token():
    session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def verify_csrf():
    sent = request.headers.get(CSRF_HEADER, "")
    expected = session.get("csrf")
    if not expected or not sent or not secrets.compare_digest(sent, expected):
        abort(403, description="csrf")


def verify_origin():
    """Defensa adicional: si el navegador envia Origin, debe ser este mismo sitio."""
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).netloc != request.host:
        abort(403, description="origin")


# ---------------------------------------------------------------------------
# Sesion de usuario
# ---------------------------------------------------------------------------

def start_session(user):
    from app.models.user import AuthSession

    end_session()
    now = int(time.time())
    sid = secrets.token_hex(32)
    AuthSession.query.filter(AuthSession.expires_at <= now).delete()
    db.session.add(AuthSession(id=sid, user_id=user.id,
                               expires_at=now + current_app.config["SESSION_ABSOLUTE_SECONDS"]))
    session.permanent = True
    session["sid"] = sid
    session["fp"] = user.fingerprint
    request.environ[_USER_KEY] = user
    return rotate_csrf_token()


def end_session():
    from app.models.user import AuthSession

    sid = session.get("sid")
    if sid:
        AuthSession.query.filter_by(id=sid).delete()
    session.clear()
    request.environ[_USER_KEY] = None


def current_user():
    if _USER_KEY in request.environ:
        return request.environ[_USER_KEY]
    from app.models.user import AuthSession, User

    user = None
    sid, fp = session.get("sid"), session.get("fp")
    if sid and fp:
        active = db.session.get(AuthSession, sid)
        if active and active.expires_at > time.time():
            candidate = db.session.get(User, active.user_id)
            if candidate and candidate.is_active and not candidate.email_verification_pending:
                if secrets.compare_digest(candidate.fingerprint, fp):
                    user = candidate
    if user is None and (sid or session.get("uid")):
        for key in ("sid", "uid", "fp", "iat"):
            session.pop(key, None)
    request.environ[_USER_KEY] = user
    return user


def require_staff():
    user = current_user()
    if user is None:
        abort(401)
    if not user.is_staff:
        abort(403)
    return user


def require_admin():
    user = current_user()
    if user is None:
        abort(401)
    if not user.is_admin:
        abort(403, description="forbidden")
    return user


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        require_admin()
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Limite de intentos en memoria (por proceso)
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self._hits = {}
        self._lock = threading.Lock()

    def hit(self, key):
        """Registra un intento. Devuelve (permitido, segundos_para_reintentar)."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False, int(self.window - (now - bucket[0])) + 1
            bucket.append(now)
            if len(self._hits) > 10000:
                self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < self.window}
            return True, 0

    def reset(self, key):
        with self._lock:
            self._hits.pop(key, None)


def limiter(name):
    limits = {
        "login": (5, 900),        # 5 intentos por correo e IP cada 15 minutos
        "login_ip": (20, 900),    # 20 intentos por IP cada 15 minutos
        "chat": (10, 60),
        "checkout": (10, 600),
        "lookup": (10, 600),
        "register": (5, 600),         # 5 registros por IP cada 10 minutos
        "forgot_ip": (5, 600),        # 5 solicitudes de recuperacion por IP cada 10 minutos
        "forgot_email": (3, 900),     # 3 correos de recuperacion por cuenta cada 15 minutos
        "resend_ip": (5, 600),
        "resend_email": (3, 900),
        "token": (10, 600),           # 10 usos de enlace (activar o restablecer) por IP cada 10 minutos
    }
    store = current_app.extensions.setdefault("ferrepro_limits", {})
    if name not in store:
        store[name] = RateLimiter(*limits[name])
    return store[name]


def client_ip():
    return request.remote_addr or "unknown"
