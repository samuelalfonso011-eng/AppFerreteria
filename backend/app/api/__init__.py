from flask import Blueprint, abort, request

from app.utils.security import verify_csrf, verify_origin

api_bp = Blueprint("api", __name__, url_prefix="/api")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@api_bp.before_request
def protect_writes():
    """Toda escritura exige JSON, mismo origen y token CSRF de la sesion."""
    if request.method in SAFE_METHODS:
        return
    verify_origin()
    verify_csrf()
    if request.method != "DELETE" and not request.is_json:
        abort(415)


_admin_nested = False


def register_api(app):
    global _admin_nested
    # Los modulos agregan sus rutas al importarse (una sola vez por proceso)
    from app.api import auth, orders, public  # noqa: F401
    from app.api.admin import admin_bp
    if not _admin_nested:
        # Anidado bajo /api: hereda la verificacion CSRF y de origen de api_bp
        api_bp.register_blueprint(admin_bp)
        _admin_nested = True
    app.register_blueprint(api_bp)
