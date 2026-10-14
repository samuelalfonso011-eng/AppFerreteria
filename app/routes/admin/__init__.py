from app.routes.admin.dashboard import admin_dashboard_bp
from app.routes.admin.products import admin_products_bp
from app.routes.admin.categories import admin_categories_bp
from app.routes.admin.inventory import admin_inventory_bp
from app.routes.admin.orders import admin_orders_bp
from app.routes.admin.customers import admin_customers_bp
from app.routes.admin.payments import admin_payments_bp
from app.routes.admin.settings import admin_settings_bp

__all__ = [
    'admin_dashboard_bp',
    'admin_products_bp',
    'admin_categories_bp',
    'admin_inventory_bp',
    'admin_orders_bp',
    'admin_customers_bp',
    'admin_payments_bp',
    'admin_settings_bp',
]
