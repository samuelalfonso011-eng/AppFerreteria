import logging
import os

from flask import Flask, abort, request, send_from_directory
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.config import config_by_name
from app.extensions import db

logger = logging.getLogger(__name__)

# Unicos archivos del frontend que se sirven. Nada mas de la raiz (ni backend/, ni .env) es accesible.
FRONTEND_FILES = {
    "index.html", "admin.html", "styles.css", "theme.css", "admin.css",
    "app.js", "admin.js", "theme-init.js",
}

ERROR_MESSAGES = {
    400: ("bad_request", "La solicitud no es válida."),
    401: ("unauthorized", "Inicia sesión para continuar."),
    403: ("forbidden", "No tienes permiso para esta acción."),
    404: ("not_found", "No encontramos lo que buscas."),
    405: ("method_not_allowed", "Método no permitido."),
    413: ("too_large", "La solicitud es demasiado grande."),
    415: ("unsupported", "Envía los datos en formato JSON."),
    429: ("rate_limited", "Demasiadas solicitudes. Espera un momento."),
}


def _resolve_config_name(name):
    if name:
        return name
    env = os.getenv("FLASK_ENV", "production").lower()
    return env if env in config_by_name else "production"


def create_app(config_name=None):
    app = Flask(__name__, static_folder=None)
    config_name = _resolve_config_name(config_name)
    app.config.from_object(config_by_name[config_name])

    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if not app.testing and not uri.startswith("postgresql+psycopg://"):
        raise RuntimeError("Configura DATABASE_URL de PostgreSQL en backend/.env.")

    if config_name == "production":
        key = app.config.get("SECRET_KEY") or ""
        if len(key) < 32:
            raise RuntimeError("Produccion requiere SECRET_KEY aleatoria de al menos 32 caracteres (ver .env.example).")
        if not app.config.get("TRUSTED_HOSTS"):
            raise RuntimeError("Produccion requiere TRUSTED_HOSTS con los dominios autorizados.")
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY no esta definida (ver backend/.env.example).")

    rate = app.config["INVOICE_TAX_RATE"]
    if not rate.is_finite() or not 0 <= rate <= 1:
        raise ValueError("INVOICE_TAX_RATE debe ser una fracción entre 0 y 1.")

    hops = app.config["TRUSTED_PROXY_HOPS"]
    if not 0 <= hops <= 5:
        raise ValueError("TRUSTED_PROXY_HOPS debe estar entre 0 y 5")
    if hops:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=0, x_prefix=0)

    db.init_app(app)

    from app.utils.cache import ensure_cache_rows, register_cache_listeners
    register_cache_listeners()

    from app.api import register_api
    register_api(app)

    from app.cli import register_cli
    register_cli(app)

    if app.config.get("AUTO_CREATE_DB"):
        with app.app_context():
            from app import models as _models  # noqa: F401  (registra las tablas)
            db.create_all()
            ensure_cache_rows()
            db.session.commit()

    _register_frontend(app)
    _register_security(app)
    _register_errors(app)
    return app


def _register_frontend(app):
    root = app.config["FRONTEND_DIR"]

    def send(name):
        # max_age=0: el navegador revalida con ETag y recibe 304 si el archivo no cambio
        response = send_from_directory(root, name, max_age=0)
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/")
    def index():
        return send("index.html")

    @app.get("/admin")
    def admin_page():
        response = send("admin.html")
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @app.get("/<path:filename>")
    def frontend_file(filename):
        if filename not in FRONTEND_FILES:
            abort(404)
        return send(filename)


def _register_security(app):
    csp = "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ])

    @app.before_request
    def enforce_https():
        if app.debug or app.testing:
            return None
        if request.scheme == "http" and request.host.split(":")[0] not in ("127.0.0.1", "localhost"):
            from flask import redirect
            return redirect(request.url.replace("http://", "https://", 1), code=301)
        return None

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
            response.vary.add("Cookie")
        return response


def _register_errors(app):
    from app.services.errors import BusinessError
    from app.utils.http import json_error
    from app.utils.validation import ValidationError

    @app.errorhandler(ValidationError)
    def validation_error(error):
        return json_error(400, "validation", "Revisa los campos marcados.", fields=error.errors)

    @app.errorhandler(BusinessError)
    def business_error(error):
        payload = error.to_dict()
        return json_error(error.status, payload.pop("error"), payload.pop("message"), **payload)

    @app.errorhandler(HTTPException)
    def http_error(error):
        if not request.path.startswith("/api/"):
            return error
        code, message = ERROR_MESSAGES.get(error.code, ("error", error.description or "Error"))
        if error.code == 403 and error.description == "csrf":
            code, message = "csrf", "Tu sesión de seguridad venció. Vuelve a intentarlo."
        elif error.code == 403 and error.description == "origin":
            code = "origin"
        return json_error(error.code, code, message)

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        logger.exception("Error de base de datos")
        return json_error(500, "server_error", "No pudimos completar la operación. Intenta de nuevo.")

    @app.errorhandler(Exception)
    def unexpected_error(error):
        db.session.rollback()
        logger.exception("Error no controlado")
        return json_error(500, "server_error", "Ocurrió un error inesperado. Intenta de nuevo.")
