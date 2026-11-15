"""
Suite de Pruebas Automatizadas para la Versión 1.3.0
Cubre los 9 criterios de aceptación de la versión 1.3.0:
1. Política de reembolsos (Ley 1480 y Decreto 587) y enlaces en Footer (ES/EN).
2. Generación automática de Factura Electrónica (FE-XXXX) con CUFE y vista imprimible.
3. Ocultamiento de banners de registro para usuarios autenticados.
4. Dashboard administrativo con 3 lienzos de gráficos y endpoint GET /admin/api/metrics.
5. Idempotencia y blindaje contra doble cobro en pagos / pedidos.
6. Invalidación automática del caché en base de datos mediante eventos SQLAlchemy.
7. Blindaje Anti-Spam multicapa (honeypot, enlaces excesivos, rate limiting).
8. Optimización y compresión de imágenes de producto mediante Pillow (Lanczos max 1200px).
9. Redirección HTTPS y cabeceras HTTP de seguridad (HSTS, nosniff, SAMEORIGIN, Referrer-Policy).
"""

import io
import time
from decimal import Decimal
import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models.user import User, Address
from app.models.product import Product
from app.models.category import Category
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.invoice import ElectronicInvoice
from app.models.contact import ContactMessage
from app.services.order_service import OrderService
from app.services.cart_service import CartService
from app.services.payment_service import PaymentService
from app.services.invoice_service import InvoiceService
from app.utils.cache import cache
from app.utils.anti_spam import (
    is_honeypot_triggered,
    contains_excessive_links,
    check_rate_limit,
    render_rate_limit_error
)
from app.utils.image_optimizer import optimize_product_image


# ==============================================================================
# CRITERIO 1: POLÍTICA DE REEMBOLSOS Y FOOTER (ES / EN)
# ==============================================================================

def test_criterio_1_refunds_policy_and_footer(client):
    """Verifica que /politica-de-reembolsos responde 200 y está enlazada en el footer en ES y EN."""
    # 1. Acceso directo a la página legal de reembolsos
    res = client.get('/politica-de-reembolsos')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert "Ley 1480 de 2011" in html
    assert "Decreto 587 de 2016" in html
    assert "retracto" in html.lower()
    assert "5 días" in html or "cinco (5) días" in html

    # 2. Enlace en el footer en español
    res_home = client.get('/')
    assert res_home.status_code == 200
    assert '/politica-de-reembolsos' in res_home.data.decode('utf-8')
    assert "Reembolsos" in res_home.data.decode('utf-8')

    # 3. Alternar idioma a inglés y verificar enlace en footer
    client.get('/set-language/en')
    res_en = client.get('/')
    assert res_en.status_code == 200
    html_en = res_en.data.decode('utf-8')
    assert '/politica-de-reembolsos' in html_en
    assert "Refunds" in html_en

    # Restaurar idioma a español
    client.get('/set-language/es')


# ==============================================================================
# CRITERIO 2: FACTURA ELECTRÓNICA DIAN (FE-XXXX) CON CUFE Y VISTA IMPRIMIBLE
# ==============================================================================

def test_criterio_2_electronic_invoice_generation_and_view(client, app):
    """Verifica generación de factura electrónica FE-XXXX, CUFE, IVA 19% y vista en /orders/<id>/invoice."""
    with app.app_context():
        customer = User.query.filter_by(email="cliente@correo.com").first()
        prod = Product.query.first()

        # Agregar items y crear pedido mediante OrderService
        CartService.add_item(product_id=prod.id, quantity=2, user=customer)
        order = OrderService.create_order(
            user=customer,
            shipping_data={
                'recipient_name': customer.full_name,
                'phone': '300 123 4567',
                'department': 'Antioquia',
                'city': 'Medellín',
                'neighborhood': 'Laureles',
                'street_address': 'Carrera 43A # 1-50'
            }
        )
        order.fiscal_doc_type = "CC"
        order.fiscal_doc_number = "1020304050"
        order.fiscal_name = "Juan Perez"
        order.fiscal_email = "cliente@correo.com"
        db.session.commit()

        # Procesar pago simulado con éxito -> dispara emisión de factura electrónica
        payment = PaymentService.process_payment(
            order=order,
            payment_method=PaymentMethod.SIMULATED_CARD,
            idempotency_key="pay-inv-test-001"
        )
        assert payment is not None
        assert payment.status == "APPROVED"

        # Verificar que la factura fue emitida
        invoice = ElectronicInvoice.query.filter_by(order_id=order.id).first()
        assert invoice is not None
        assert invoice.invoice_number.startswith("FE-")
        assert len(invoice.cufe) >= 64
        assert invoice.tax_rate == Decimal("19.00")
        assert invoice.total == order.total
        assert "<svg" in invoice.qr_svg
        order_id = order.id
        order_num = order.order_number

    # Iniciar sesión como el cliente y consultar la factura imprimible
    client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}, follow_redirects=True)

    # Ruta estándar /orders/<id>/invoice
    res_inv = client.get(f'/orders/{order_id}/invoice')
    assert res_inv.status_code == 200
    html_inv = res_inv.data.decode('utf-8')
    assert "Factura Electrónica" in html_inv
    assert invoice.invoice_number in html_inv
    assert "CUFE" in html_inv
    assert invoice.cufe in html_inv
    assert "1020304050" in html_inv
    assert "IVA 19%" in html_inv
    assert "<svg" in html_inv

    # Ruta amigable /mis-pedidos/<order_number>/factura
    res_inv_slug = client.get(f'/mis-pedidos/{order_num}/factura')
    assert res_inv_slug.status_code == 200

    # Cerrar sesión
    client.post('/logout', follow_redirects=True)


# ==============================================================================
# CRITERIO 3: OCULTAMIENTO DE BANNERS DE REGISTRO CUANDO SE ESTÁ AUTENTICADO
# ==============================================================================

def test_criterio_3_registration_banner_hidden_for_authenticated_users(client):
    """Verifica que el banner 'Regístrate hoy' se oculta cuando el usuario ha iniciado sesión."""
    # 1. Como visitante anónimo: debe ver la invitación a registrarse
    res_anon = client.get('/')
    assert res_anon.status_code == 200
    html_anon = res_anon.data.decode('utf-8')
    assert "Regístrate hoy" in html_anon or "regístrate hoy" in html_anon.lower()

    # 2. Iniciar sesión como cliente
    client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}, follow_redirects=True)

    # 3. Como usuario autenticado: no debe ver el banner de registro, sino el panel de cliente
    res_auth = client.get('/')
    assert res_auth.status_code == 200
    html_auth = res_auth.data.decode('utf-8')
    assert "Regístrate hoy y gestiona tus pedidos" not in html_auth
    assert "Bienvenido de nuevo" in html_auth
    assert "Ver Mis Pedidos" in html_auth

    # Cerrar sesión
    client.post('/logout', follow_redirects=True)


# ==============================================================================
# CRITERIO 4: DASHBOARD ADMIN CON 3 GRÁFICOS Y ENDPOINT GET /admin/api/metrics
# ==============================================================================

def test_criterio_4_admin_dashboard_charts_and_metrics_api(client):
    """Verifica que el dashboard administrativo incluye 3 lienzos canvas y /admin/api/metrics responde JSON."""
    # Intentar como anónimo: debe redirigir a login
    res_anon = client.get('/admin/api/metrics')
    assert res_anon.status_code in (302, 401, 403)

    # Iniciar sesión como administrador
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)

    # 1. Comprobar endpoint JSON de métricas
    res_api = client.get('/admin/api/metrics')
    assert res_api.status_code == 200
    assert res_api.is_json
    data = res_api.get_json()
    assert 'sales_trend' in data
    assert 'top_products' in data
    assert 'orders_by_status' in data
    assert 'budget_stats' in data
    assert 'storage_stats' in data

    # 2. Comprobar que la vista del Dashboard renderiza los 3 lienzos de Chart.js
    res_dash = client.get('/admin/')
    assert res_dash.status_code == 200
    html_dash = res_dash.data.decode('utf-8')
    assert 'id="salesTrendChart"' in html_dash
    assert 'id="topProductsChart"' in html_dash
    assert 'id="orderStatusChart"' in html_dash
    assert "chart.js" in html_dash.lower()

    client.post('/logout', follow_redirects=True)


# ==============================================================================
# CRITERIO 5: IDEMPOTENCIA Y PROTECCIÓN CONTRA DOBLE COBRO EN CHECKOUT
# ==============================================================================

def test_criterio_5_idempotency_prevents_duplicate_charges(app):
    """Verifica que peticiones repetidas con la misma llave de idempotencia evitan el doble cobro."""
    with app.app_context():
        customer = User.query.filter_by(email="cliente@correo.com").first()
        prod = Product.query.first()

        CartService.add_item(product_id=prod.id, quantity=1, user=customer)
        order = OrderService.create_order(
            user=customer,
            shipping_data={
                'recipient_name': customer.full_name,
                'phone': '300 123 4567',
                'department': 'Antioquia',
                'city': 'Medellín',
                'neighborhood': 'Laureles',
                'street_address': 'Carrera 43A # 1-50'
            }
        )

        # Primer cobro con llave de idempotencia
        pay1 = PaymentService.process_payment(
            order=order,
            payment_method=PaymentMethod.SIMULATED_CARD,
            idempotency_key="tx-idem-key-999"
        )
        assert pay1.status == "APPROVED"

        # Segundo cobro simultáneo o repetido con la MISMA llave de idempotencia
        pay2 = PaymentService.process_payment(
            order=order,
            payment_method=PaymentMethod.SIMULATED_CARD,
            idempotency_key="tx-idem-key-999"
        )
        assert pay2.id == pay1.id  # Retorna el mismo objeto de pago sin duplicar

        # Tercer intento sin llave pero sobre orden ya pagada
        pay3 = PaymentService.process_payment(
            order=order,
            payment_method=PaymentMethod.SIMULATED_CARD
        )
        assert pay3.id == pay1.id

        # Total de pagos en base de datos debe ser exactamente 1
        count_payments = Payment.query.filter_by(order_id=order.id).count()
        assert count_payments == 1


# ==============================================================================
# CRITERIO 6: INVALIDACIÓN AUTOMÁTICA DEL CACHÉ EN BASE DE DATOS
# ==============================================================================

def test_criterio_6_database_events_auto_invalidate_cache(app):
    """Verifica que inserciones/actualizaciones en modelos de BD invalidan las claves del caché."""
    with app.app_context():
        # Poblar manualmente claves de caché simuladas
        cache.set('products:catalog:all', [{'id': 1, 'name': 'Martillo'}], ttl=300)
        cache.set('categories:active_list', [{'id': 1, 'name': 'Herramientas'}], ttl=300)
        cache.set('orders:summary:count', 42, ttl=300)

        assert cache.get('products:catalog:all') is not None
        assert cache.get('categories:active_list') is not None
        assert cache.get('orders:summary:count') is not None

        # 1. Modificar un producto y hacer commit
        prod = Product.query.first()
        prod.stock += 5
        db.session.commit()

        # Claves de productos deben haberse invalidado automáticamente
        assert cache.get('products:catalog:all') is None
        # La de categorías u órdenes que no fueron modificadas se conservan
        assert cache.get('categories:active_list') is not None

        # 2. Modificar una categoría
        cat = Category.query.first()
        cat.name = "Herramientas de Precisión"
        db.session.commit()

        # Ahora categorías también se invalidó
        assert cache.get('categories:active_list') is None


# ==============================================================================
# CRITERIO 7: BLINDAJE ANTI-SPAM (HONEYPOT, TIEMPO, ENLACES, RATE LIMIT)
# ==============================================================================

def test_criterio_7_anti_spam_protections(client, app):
    """Verifica rechazo de bots mediante honeypot, links excesivos y rate limiting."""
    # 1. Honeypot en Contacto: Si website_url está lleno, no debe crear ContactMessage
    with app.app_context():
        initial_msg_count = ContactMessage.query.count()

    res_bot = client.post('/contacto', data={
        'full_name': 'Bot Spammer',
        'email': 'bot@spam.com',
        'subject': 'general',
        'message': 'Compra seguidores y criptomonedas aquí',
        'website_url': 'http://malicious-spam-url.com'  # Honeypot lleno
    }, follow_redirects=True)

    assert res_bot.status_code == 200
    with app.app_context():
        assert ContactMessage.query.count() == initial_msg_count  # Cero persistencia

    # 2. Detección de enlaces excesivos
    res_links = client.post('/contacto', data={
        'full_name': 'SEO Spammer',
        'email': 'seo@spam.com',
        'subject': 'general',
        'message': 'Visita http://enlace1.com y también https://enlace2.com o www.enlace3.com',
        'website_url': ''  # Honeypot vacío
    }, follow_redirects=True)
    assert "demasiados enlaces sospechosos" in res_links.data.decode('utf-8')

    # 3. Helpers unitarios anti-spam
    assert is_honeypot_triggered({'website_url': 'filled_value'}) is True
    assert is_honeypot_triggered({'website_url': ''}) is False
    assert contains_excessive_links("Texto normal sin links") is False
    assert contains_excessive_links("http://site1.com http://site2.com http://site3.com", max_links=2) is True

    # 4. Verificación de Rate Limit
    app.config['ENFORCE_RATE_LIMIT'] = True
    try:
        assert check_rate_limit("test_action_limit", limit=2, window_seconds=10) is True
        assert check_rate_limit("test_action_limit", limit=2, window_seconds=10) is True
        # El tercer intento supera el límite de 2
        assert check_rate_limit("test_action_limit", limit=2, window_seconds=10) is False
    finally:
        app.config['ENFORCE_RATE_LIMIT'] = False

    # Renderizado 429
    err_res = render_rate_limit_error("Límite superado de prueba")
    assert err_res[1] == 429


# ==============================================================================
# CRITERIO 8: OPTIMIZACIÓN Y COMPRESIÓN DE IMÁGENES CON PILLOW
# ==============================================================================

def test_criterio_8_pillow_image_optimization(app):
    """Verifica que Pillow escala imágenes gigantes a máximo 1200px y las comprime eficientemente."""
    # Crear una imagen gigante en memoria (2400 x 1800 px)
    img_large = Image.new('RGB', (2400, 1800), color=(255, 209, 0))
    buffer = io.BytesIO()
    img_large.save(buffer, format='JPEG', quality=95)
    buffer.seek(0)
    original_size = len(buffer.getvalue())

    with app.app_context():
        # Ejecutar optimizador con FileStorage
        fs = FileStorage(stream=buffer, filename="taladro_gigante.jpg", content_type="image/jpeg")
        optimized_filename = optimize_product_image(fs, target_format='webp', quality=80)
        assert optimized_filename is not None
        assert optimized_filename.endswith(".webp")

        # Cargar la imagen optimizada desde el disco para verificar dimensiones
        import os
        from flask import current_app
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], optimized_filename)
        assert os.path.exists(filepath)

        with Image.open(filepath) as img_opt:
            w, h = img_opt.size
            assert max(w, h) <= 1200
            assert img_opt.format == 'WEBP'
            optimized_size = os.path.getsize(filepath)
            # Debe pesar significativamente menos que la imagen original de 2400x1800
            assert optimized_size < original_size

        # Limpiar archivo de prueba
        try:
            os.remove(filepath)
        except OSError:
            pass


# ==============================================================================
# CRITERIO 9: REDIRECCIÓN HTTPS Y CABECERAS DE SEGURIDAD HTTP
# ==============================================================================

def test_criterio_9_security_headers_and_https_redirection(client, app):
    """Verifica cabeceras HTTP de seguridad (nosniff, SAMEORIGIN, Referrer-Policy) y redirección HTTPS."""
    # 1. Petición normal: verificar cabeceras de seguridad
    res = client.get('/')
    assert res.status_code == 200
    assert res.headers.get('X-Content-Type-Options') == 'nosniff'
    assert res.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert res.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'

    # 2. Forzar HTTPS en configuración y verificar redirección 301
    app.config['FORCE_HTTPS'] = True
    # Petición entrante HTTP con cabecera de proxy indicando http
    res_http = client.get('/', base_url='http://ferreteria.com', headers={'X-Forwarded-Proto': 'http'})
    assert res_http.status_code == 301
    assert res_http.headers.get('Location', '').startswith('https://')

    # Petición HTTPS debe responder 200 y contener HSTS
    res_https = client.get('/', base_url='https://ferreteria.com', headers={'X-Forwarded-Proto': 'https'})
    assert res_https.status_code == 200
    assert 'Strict-Transport-Security' in res_https.headers

    # Restaurar configuración
    app.config['FORCE_HTTPS'] = False
