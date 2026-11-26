"""Backoffice. El guardia vive en el blueprint: ninguna ruta admin puede olvidar la proteccion."""
from flask import Blueprint

from app.utils.security import require_admin

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
def guard():
    require_admin()  # 401 sin sesion, 403 si la cuenta no es administradora


from app.api.admin import analytics, benchmarks, catalog, customers, dashboard, integrity, inventory, orders, settings, users  # noqa: E402,F401
