from flask import Blueprint, abort, request

from app.utils.security import current_user, verify_csrf, verify_origin

api_bp = Blueprint("api", __name__, url_prefix="/api")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@api_bp.before_request
def protect_writes():
    """Protege las escrituras con mismo origen y CSRF."""
    if request.method in SAFE_METHODS:
        return
    verify_origin()
    verify_csrf()
    if request.endpoint in {"api.create_order", "api.register"}:
        user = current_user()
        if user and user.role == user.ROLE_EMPLOYEE:
            abort(403)
    if request.endpoint == "api.register_payment" and request.mimetype == "multipart/form-data":
        request.max_content_length = 5 * 1024 * 1024 + 64 * 1024
        request.max_form_parts = 6
        return
    if request.method != "DELETE" and not request.is_json:
        abort(415)


_admin_nested = False


def register_api(app):
    global _admin_nested
    # Los modulos agregan sus rutas al importarse (una sola vez por proceso)
    from app.api import auth, billing, chat, orders, public  # noqa: F401
    from app.api.admin import admin_bp
    if not _admin_nested:
        # Anidado bajo /api: hereda la verificacion CSRF y de origen de api_bp
        api_bp.register_blueprint(admin_bp)
        _admin_nested = True
    app.register_blueprint(api_bp)
