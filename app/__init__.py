import os
from decimal import Decimal
from datetime import datetime
from flask import Flask, render_template
from app.config import config_by_name
from app.extensions import db, migrate, login_manager, csrf
from app.cli import register_cli_commands
from app.models.user import User
from app.models.setting import StoreSetting
from app.services.cart_service import CartService


def create_app(config_name: str = None) -> Flask:
    """Fábrica de aplicaciones (Application Factory) para Flask."""
    app = Flask(__name__)

    # Determinar configuración
    if not config_name:
        env_mode = os.getenv('FLASK_ENV', 'development').lower()
        config_name = 'development' if env_mode == 'development' else ('testing' if env_mode == 'testing' else 'production')

    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    # Asegurar directorio de subida de imágenes locales
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Cargar usuario para Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Registrar comandos CLI
    register_cli_commands(app)

    # Context Processors globales para plantillas Jinja2
    @app.context_processor
    def inject_global_data():
        settings = StoreSetting.get_settings()
        from flask_login import current_user
        from flask import session
        from app.translations import translate
        cart_info = CartService.get_cart_data(current_user)
        current_lang = session.get('lang', 'es')
        return {
            'store_settings': settings,
            'cart_item_count': cart_info['total_items'],
            'cart_subtotal': cart_info['subtotal'],
            'current_year': datetime.now().year,
            'current_lang': current_lang,
            't': lambda key, default=None: translate(key, current_lang, default)
        }

    # Filtros personalizados de Jinja2
    @app.template_filter('currency')
    def currency_filter(value):
        """Formatea un número o Decimal a formato de moneda con separador de miles."""
        if value is None:
            return "$ 0"
        try:
            val = Decimal(str(value))
            # Formatear con separador de miles estándar (ej. $ 150.000)
            return f"$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return f"$ {value}"

    @app.template_filter('date_format')
    def date_format_filter(value, format="%d/%m/%Y %I:%M %p"):
        """Formatea fechas en plantillas."""
        if not value:
            return ""
        return value.strftime(format)

    # Registrar Blueprints de la tienda pública
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.products import products_bp
    from app.routes.cart import cart_bp
    from app.routes.checkout import checkout_bp
    from app.routes.orders import orders_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(orders_bp)

    # Registrar Blueprints del panel administrativo
    from app.routes.admin.dashboard import admin_dashboard_bp
    from app.routes.admin.products import admin_products_bp
    from app.routes.admin.categories import admin_categories_bp
    from app.routes.admin.inventory import admin_inventory_bp
    from app.routes.admin.orders import admin_orders_bp
    from app.routes.admin.customers import admin_customers_bp
    from app.routes.admin.payments import admin_payments_bp
    from app.routes.admin.settings import admin_settings_bp

    app.register_blueprint(admin_dashboard_bp)
    app.register_blueprint(admin_products_bp)
    app.register_blueprint(admin_categories_bp)
    app.register_blueprint(admin_inventory_bp)
    app.register_blueprint(admin_orders_bp)
    app.register_blueprint(admin_customers_bp)
    app.register_blueprint(admin_payments_bp)
    app.register_blueprint(admin_settings_bp)

    # Manejo centralizado de errores HTTP sin exponer trazas internas
    @app.errorhandler(400)
    def bad_request_error(error):
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app
