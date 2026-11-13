import os
from decimal import Decimal
from datetime import datetime
import secrets
from flask import Flask, render_template, g
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

    if config_name not in config_by_name:
        raise ValueError("Entorno de configuración desconocido")
    app.config.from_object(config_by_name[config_name])
    if config_name == 'production':
        key = app.config.get('SECRET_KEY') or ''
        if len(key) < 32 or key.startswith(('cambiar_', 'ferreteria-dev-')):
            raise RuntimeError("Producción requiere una SECRET_KEY aleatoria de al menos 32 caracteres")
        if not app.config.get('TRUSTED_HOSTS'):
            raise RuntimeError("Producción requiere TRUSTED_HOSTS con los dominios autorizados")


    # Seguridad: nunca arrancar fuera de desarrollo/pruebas sin una SECRET_KEY real
    if not app.config.get('SECRET_KEY') and not app.testing:
        raise RuntimeError("SECRET_KEY no está definida. Configúrala como variable de entorno (ver .env.example).")

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
        try:
            identifier, fingerprint = user_id.split(':', 1)
            user = db.session.get(User, int(identifier))
        except (AttributeError, TypeError, ValueError):
            return None
        if user and user.is_active and secrets.compare_digest(user.session_fingerprint, fingerprint):
            return user
        return None

    # Registrar comandos CLI
    register_cli_commands(app)

    # Registrar listeners de invalidación automática de caché
    from app.utils.cache import register_cache_invalidation_listeners
    register_cache_invalidation_listeners()

    # Context Processors globales para plantillas Jinja2
    @app.context_processor
    def inject_global_data():
        settings = StoreSetting.get_settings()
        from flask_login import current_user
        from flask import session
        from app.translations import translate, translate_category
        cart_info = CartService.get_cart_data(current_user)
        current_lang = session.get('lang', 'es')
        return {
            'store_settings': settings,
            'cart_item_count': cart_info['total_items'],
            'cart_subtotal': cart_info['subtotal'],
            'current_year': datetime.now().year,
            'csp_nonce': getattr(g, 'csp_nonce', ''),
            'current_lang': current_lang,
            't': lambda key, default=None: translate(key, current_lang, default),
            't_category': lambda name: translate_category(name, current_lang)
        }

    # Filtros personalizados de Jinja2
    from app.utils.timezone import format_bogota, to_bogota

    @app.template_filter('currency')
    def currency_filter(value):
        """Formatea un número o Decimal a formato de moneda con separador de miles."""
        if value is None:
            return "$ 0"
        try:
            val = Decimal(str(value))
            # Pesos colombianos: sin decimales ($ 150.000); solo se muestran centavos si existen
            if val == val.to_integral_value():
                return f"$ {val:,.0f}".replace(",", ".")
            return f"$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return f"$ {value}"

    @app.template_filter('date_format')
    def date_format_filter(value, format="%d/%m/%Y %I:%M %p"):
        """Formatea fechas en plantillas en hora oficial de Colombia (UTC-5)."""
        return format_bogota(value, format)

    @app.template_filter('bogota_time')
    def bogota_time_filter(value, fmt="%d/%m/%Y %I:%M %p"):
        """Formatea fecha y hora en hora oficial de Colombia."""
        return format_bogota(value, fmt)

    @app.template_filter('bogota_date')
    def bogota_date_filter(value):
        """Formatea solo la fecha en hora oficial de Colombia."""
        return format_bogota(value, "%d/%m/%Y")

    # Registrar Blueprints de la tienda pública
    from app.routes.public import public_bp
    from app.routes.auth import auth_bp
    from app.routes.products import products_bp
    from app.routes.cart import cart_bp
    from app.routes.checkout import checkout_bp
    from app.routes.orders import orders_bp, orders_invoice_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(orders_invoice_bp)

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

    # ProxyFix para detección precisa de encabezados HTTPS en despliegues con proxy inverso
    from werkzeug.middleware.proxy_fix import ProxyFix
    proxy_hops = app.config['TRUSTED_PROXY_HOPS']
    if not 0 <= proxy_hops <= 5:
        raise ValueError("TRUSTED_PROXY_HOPS debe estar entre 0 y 5")
    if proxy_hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops, x_proto=proxy_hops,
                               x_host=0, x_prefix=0)

    # Middleware para forzar HTTPS si FORCE_HTTPS está activo o en producción pública
    from flask import request, redirect
    @app.before_request
    def enforce_https():
        force_https = os.getenv('FORCE_HTTPS', 'false').lower() in ('true', '1', 'yes') or app.config.get('FORCE_HTTPS')
        if force_https or (not app.debug and not app.testing and request.host.split(':')[0] not in ('127.0.0.1', 'localhost', 'testserver')):
            # Detectar protocolo (compatible con X-Forwarded-Proto vía ProxyFix)
            if request.scheme == 'http':
                url = request.url.replace('http://', 'https://', 1)
                return redirect(url, code=301)

    # Nonce criptográfico por petición para scripts inline autorizados por la CSP
    @app.before_request
    def generate_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    def build_csp(nonce: str) -> str:
        return "; ".join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net",
            # Los estilos inline (atributos style=) son muy numerosos; el riesgo de inyección CSS es bajo
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' data: https://fonts.gstatic.com",
            "img-src 'self' data: blob:",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'self'",
        ])

    # Cabeceras HTTP de seguridad avanzada (v1.3.0)
    @app.after_request
    def set_security_headers(response):
        csp_header = ('Content-Security-Policy-Report-Only'
                      if os.getenv('CSP_REPORT_ONLY', 'false').lower() in ('true', '1', 'yes')
                      else 'Content-Security-Policy')
        response.headers[csp_header] = build_csp(getattr(g, 'csp_nonce', ''))
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        force_https = os.getenv('FORCE_HTTPS', 'false').lower() in ('true', '1', 'yes') or app.config.get('FORCE_HTTPS')
        if request.is_secure or force_https:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # Manejo centralizado de errores HTTP sin exponer trazas internas
    @app.errorhandler(400)
    def bad_request_error(error):
        from flask import jsonify
        if request.is_json:
            return jsonify(success=False, message='Solicitud inválida o sesión de seguridad vencida.'), 400
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def too_many_requests_error(error):
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app
