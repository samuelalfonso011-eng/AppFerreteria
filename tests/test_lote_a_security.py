"""Regresión del Lote A: seguridad crítica y bugs que rompían funcionalidad."""
from decimal import Decimal
import pytest
from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderStatus
from app.models.payment import PaymentMethod
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.payment_service import payment_service
from app.routes.auth import is_safe_next_url, generate_reset_token, verify_reset_token

SHIPPING = {
    'recipient_name': 'Juan Perez', 'phone': '3001234567', 'department': 'Antioquia',
    'city': 'Medellín', 'neighborhood': 'Laureles', 'street_address': 'Circular 4 # 73-20',
}


def _login(client, email, password):
    return client.post('/login', data={'email': email, 'password': password})


def _pending_order(user):
    CartService.add_item(product_id=1, quantity=1, user=user)
    return OrderService.create_order(user=user, shipping_data=SHIPPING)


# ---- S1 / S2 / B6: pagos ----
def test_payment_blocked_on_cancelled_order(app):
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        order = _pending_order(user)
        OrderService.cancel_by_customer(order.id, user.id, 'prueba')
        stock_after_cancel = db.session.get(Product, 1).stock
        with pytest.raises(ValueError):
            payment_service.process_payment(order, PaymentMethod.SIMULATED_CARD, 'approve')
        assert db.session.get(Order, order.id).status == OrderStatus.CANCELLED
        assert db.session.get(Product, 1).stock == stock_after_cancel


def test_payment_simulation_disabled_by_flag(app):
    app.config['PAYMENTS_SIMULATION_ENABLED'] = False
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        order = _pending_order(user)
        with pytest.raises(ValueError):
            payment_service.process_payment(order, PaymentMethod.SIMULATED_CARD, 'approve')
        assert db.session.get(Order, order.id).status == OrderStatus.PENDING_CONFIRMATION


def test_production_defaults_disable_simulation_and_require_secret():
    from app.config import ProductionConfig
    assert ProductionConfig.PAYMENTS_SIMULATION_ENABLED is False


# ---- S3: open redirect ----
@pytest.mark.parametrize('url,ok', [
    ('/mis-pedidos/', True), ('//evil.com', False), ('/\\evil.com', False),
    ('https://evil.com', False), ('javascript:alert(1)', False), ('', False), (None, False),
])
def test_is_safe_next_url(url, ok):
    assert is_safe_next_url(url) is ok


def test_login_ignores_external_next(client):
    res = client.post('/login?next=//evil.com',
                      data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'})
    assert res.status_code == 302
    assert 'evil.com' not in res.headers['Location']


# ---- S7: reset de contraseña ----
def test_reset_token_is_single_use(app):
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        token = generate_reset_token(user.id)
        assert verify_reset_token(token) == user.id
        user.set_password('OtraClave123*')
        db.session.commit()
        assert verify_reset_token(token) is None


def test_forgot_password_same_response_and_no_link_in_production(app, client):
    app.config['TESTING'] = False
    app.debug = False
    r1 = client.post('/recuperar-password', data={'email': 'cliente@correo.com'})
    r2 = client.post('/recuperar-password', data={'email': 'noexiste@correo.com'})
    assert r1.status_code == r2.status_code == 302
    assert r1.headers['Location'] == r2.headers['Location']


# ---- B1 / B4: pedidos manuales de admin ----
def test_admin_manual_order_with_customer_selected(app, client):
    _login(client, 'admin@ferreteria.com', 'AdminPass123*')
    with app.app_context():
        cid = User.query.filter_by(email='cliente@correo.com').first().id
    res = client.post('/admin/pedidos/nuevo', data={
        'customer_user_id': str(cid), 'shipping_type': 'pickup', 'qty_1': '1',
        'status': 'CONFIRMED', 'payment_method': PaymentMethod.SIMULATED_CASH_ON_DELIVERY,
        'is_paid': 'on',
    })
    assert res.status_code == 302


def test_admin_manual_order_rejects_invalid_status(app, client):
    _login(client, 'admin@ferreteria.com', 'AdminPass123*')
    for bad in ('HACKED', OrderStatus.CANCELLED):
        res = client.post('/admin/pedidos/nuevo', data={
            'shipping_type': 'pickup', 'qty_1': '1', 'status': bad,
            'payment_method': PaymentMethod.SIMULATED_CARD,
        })
        assert res.status_code == 200
    with app.app_context():
        assert db.session.get(Product, 1).stock == 10  # no se descontó stock


# ---- B2 / B3: productos ----
def _product_data(**over):
    d = {'name': 'Producto Cero', 'category_id': 1, 'sku': 'CERO-1', 'description': 'x',
         'price': '1000', 'stock': '0', 'min_stock_alert': '0', 'is_active': 'y'}
    d.update(over)
    return d


def test_create_product_with_zero_stock_and_threshold(app, client):
    _login(client, 'admin@ferreteria.com', 'AdminPass123*')
    res = client.post('/admin/productos/crear', data=_product_data())
    assert res.status_code == 302
    with app.app_context():
        p = Product.query.filter_by(sku='CERO-1').first()
        assert p is not None and p.stock == 0 and p.min_stock_alert == 0


def test_duplicate_product_name_gets_unique_slug(app, client):
    _login(client, 'admin@ferreteria.com', 'AdminPass123*')
    for sku in ('DUP-1', 'DUP-2'):
        res = client.post('/admin/productos/crear', data=_product_data(name='Producto Repetido', sku=sku))
        assert res.status_code == 302
    with app.app_context():
        slugs = {p.slug for p in Product.query.filter(Product.sku.in_(['DUP-1', 'DUP-2'])).all()}
        assert slugs == {'producto-repetido', 'producto-repetido-2'}


# ---- B9: carrito con cuerpo JSON inválido ----
def test_cart_add_with_malformed_json_returns_400(client):
    res = client.post('/carrito/agregar', data='no-es-json', content_type='application/json')
    assert res.status_code == 400
    assert res.get_json()['success'] is False


# ---- S9 / CSP ----
import re


def test_logout_requires_post(client):
    _login(client, 'cliente@correo.com', 'ClientePass123*')
    assert client.get('/logout').status_code == 405
    assert client.get('/mis-pedidos/').status_code == 200  # sigue autenticado
    res = client.post('/logout')
    assert res.status_code == 302
    assert client.get('/mis-pedidos/').status_code == 302  # ya sin sesión


def test_csp_header_has_per_request_nonce_and_no_unsafe_inline_scripts(client):
    r1, r2 = client.get('/'), client.get('/')
    csp = r1.headers['Content-Security-Policy']
    script_src = [d for d in csp.split(';') if d.strip().startswith('script-src')][0]
    assert "'unsafe-inline'" not in script_src and "'unsafe-eval'" not in script_src
    assert "object-src 'none'" in csp and "frame-ancestors 'self'" in csp
    n1 = re.search(r"'nonce-([^']+)'", csp).group(1)
    n2 = re.search(r"'nonce-([^']+)'", r2.headers['Content-Security-Policy']).group(1)
    assert n1 != n2
    assert f'nonce="{n1}"' in r1.get_data(as_text=True)


@pytest.mark.parametrize('path', ['/', '/productos/', '/productos/martillo-de-prueba', '/carrito/', '/login', '/contacto'])
def test_public_pages_have_no_inline_scripts_or_handlers(client, path):
    html = client.get(path).get_data(as_text=True)
    assert not re.search(r'<script(?![^>]*\b(src|nonce|type)=)[^>]*>', html)
    assert not re.search(r'\son(click|change|submit|error|load|mouseover|mouseout|keyup|input)=', html)


def test_admin_pages_have_no_inline_handlers(client):
    _login(client, 'admin@ferreteria.com', 'AdminPass123*')
    for path in ('/admin/', '/admin/productos/', '/admin/pedidos/nuevo', '/admin/pedidos/'):
        html = client.get(path).get_data(as_text=True)
        assert not re.search(r'<script(?![^>]*\b(src|nonce|type)=)[^>]*>', html), path
        assert not re.search(r'\son(click|change|submit|error|load|mouseover|mouseout|keyup|input)=', html), path

# ================= LOTE B =================
import io
from datetime import datetime, timedelta, timezone
from PIL import Image
from werkzeug.datastructures import FileStorage
from app.models.payment import Payment, PaymentStatus
from app.services.invoice_service import InvoiceService
from app.utils.anti_spam import reset_rate_limits
from app.utils.image_optimizer import save_optimized_image


@pytest.fixture
def rate_limited(app):
    app.config['ENFORCE_RATE_LIMIT'] = True
    reset_rate_limits()
    yield
    reset_rate_limits()
    app.config['ENFORCE_RATE_LIMIT'] = False


# ---- S4: rate limiting ----
def test_login_locks_account_after_repeated_failures_even_with_spoofed_ip(client, rate_limited):
    for i in range(5):
        res = client.post('/login', data={'email': 'cliente@correo.com', 'password': 'mala'},
                          headers={'X-Forwarded-For': f'10.0.0.{i}'})
        assert res.status_code == 200
    # ni con la clave correcta ni cambiando de IP se puede seguir probando
    res = client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'},
                      headers={'X-Forwarded-For': '10.9.9.9'})
    assert res.status_code == 429


def test_successful_login_clears_failure_counter(client, rate_limited):
    for _ in range(3):
        client.post('/login', data={'email': 'cliente@correo.com', 'password': 'mala'})
    assert client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}).status_code == 302
    client.post('/logout')
    for _ in range(3):
        client.post('/login', data={'email': 'cliente@correo.com', 'password': 'mala'})
    assert client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}).status_code == 302


def test_login_ip_limit_and_forgot_password_limit(client, rate_limited):
    codes = [client.post('/login', data={'email': f'u{i}@x.com', 'password': 'x'}).status_code for i in range(22)]
    assert codes[-1] == 429 and codes[0] == 200
    reset_rate_limits()
    codes = [client.post('/recuperar-password', data={'email': 'a@b.com'}).status_code for _ in range(7)]
    assert 429 in codes


# ---- S12: imágenes ----
def _upload(img_bytes, filename):
    return FileStorage(stream=io.BytesIO(img_bytes), filename=filename)


def _img_bytes(fmt, size=(20, 20)):
    buf = io.BytesIO()
    Image.new('RGB', size, (200, 10, 10)).save(buf, format=fmt)
    return buf.getvalue()


def test_image_valid_png_is_reencoded_as_webp(tmp_path):
    name = save_optimized_image(_upload(_img_bytes('PNG'), 'foto.png'), upload_folder=str(tmp_path))
    assert name.endswith('.webp') and (tmp_path / name).exists()


def test_image_with_wrong_real_format_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        save_optimized_image(_upload(_img_bytes('GIF'), 'falsa.png'), upload_folder=str(tmp_path))
    with pytest.raises(ValueError):
        save_optimized_image(_upload(b'<?php system(\[1]); ?>', 'shell.png'), upload_folder=str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_image_decompression_bomb_is_rejected(tmp_path):
    big = _img_bytes('PNG', size=(8000, 8000))  # 64 MP, comprime muy bien
    with pytest.raises(ValueError):
        save_optimized_image(_upload(big, 'bomba.png'), upload_folder=str(tmp_path))
    assert list(tmp_path.iterdir()) == []


# ---- B5: vencimiento de pedidos ----
def _age(order_id, minutes):
    o = db.session.get(Order, order_id)
    o.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    db.session.commit()


def test_stale_pending_orders_expire_and_restore_stock(app):
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        CartService.add_item(product_id=1, quantity=3, user=user)
        order = OrderService.create_order(user=user, shipping_data=SHIPPING)
        oid = order.id
        assert db.session.get(Product, 1).stock == 7
        _age(oid, 30)
        assert OrderService.expire_stale_pending_orders() == 0  # aún dentro del plazo
        _age(oid, 120)
        assert OrderService.expire_stale_pending_orders() == 1
        assert db.session.get(Order, oid).status == OrderStatus.CANCELLED
        assert db.session.get(Product, 1).stock == 10
        assert OrderService.expire_stale_pending_orders() == 0  # idempotente


def test_expiry_skips_orders_with_payment_in_validation_and_paid_orders(app):
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        CartService.add_item(product_id=1, quantity=1, user=user)
        waiting = OrderService.create_order(user=user, shipping_data=SHIPPING)
        payment_service.process_payment(waiting, PaymentMethod.SIMULATED_TRANSFER, 'pending')
        CartService.add_item(product_id=1, quantity=1, user=user)
        paid = OrderService.create_order(user=user, shipping_data=SHIPPING)
        payment_service.process_payment(paid, PaymentMethod.SIMULATED_CARD, 'approve')
        wid, pid = waiting.id, paid.id
        _age(wid, 500); _age(pid, 500)
        assert OrderService.expire_stale_pending_orders() == 0
        assert db.session.get(Order, wid).status == OrderStatus.PENDING_CONFIRMATION
        assert db.session.get(Order, pid).status == OrderStatus.CONFIRMED


def test_cannot_pay_an_expired_order(app):
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        CartService.add_item(product_id=1, quantity=1, user=user)
        order = OrderService.create_order(user=user, shipping_data=SHIPPING)
        _age(order.id, 500)
        OrderService.expire_stale_pending_orders()
        with pytest.raises(ValueError):
            payment_service.process_payment(order, PaymentMethod.SIMULATED_CARD, 'approve')


# ---- B7: consecutivo de facturas ----
def test_invoice_numbers_never_repeat_even_after_a_deletion(app):
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        numbers, invoices = [], []
        for _ in range(3):
            CartService.add_item(product_id=1, quantity=1, user=user)
            o = OrderService.create_order(user=user, shipping_data=SHIPPING)
            payment_service.process_payment(o, PaymentMethod.SIMULATED_CARD, 'approve')
            invoices.append(o.invoice)
        numbers = [i.invoice_number for i in invoices]
        assert numbers == ['FE-0001', 'FE-0002', 'FE-0003']
        db.session.delete(invoices[0]); db.session.commit()   # hueco al inicio: COUNT+1 repetiría FE-0003
        CartService.add_item(product_id=1, quantity=1, user=user)
        o4 = OrderService.create_order(user=user, shipping_data=SHIPPING)
        payment_service.process_payment(o4, PaymentMethod.SIMULATED_CARD, 'approve')
        assert o4.invoice.invoice_number == 'FE-0004'
        # idempotente: no crea una segunda factura para el mismo pedido
        assert InvoiceService.get_or_create_invoice_for_order(o4).id == o4.invoice.id

# ================= FASE 2: PENDIENTES =================
from app.models.category import Category


def test_currency_filter_cop_without_decimals(app):
    f = app.jinja_env.filters['currency']
    assert f(Decimal('150000.00')) == '$ 150.000'
    assert f(Decimal('1234567')) == '$ 1.234.567'
    assert f(0) == '$ 0'
    assert f(Decimal('1500.50')) == '$ 1.500,50'
    assert f(None) == '$ 0'


def test_checkout_blocks_when_stock_dropped_with_clear_message(app, client):
    _login(client, 'cliente@correo.com', 'ClientePass123*')
    client.post('/carrito/agregar', json={'product_id': 1, 'quantity': 5})
    # misma sesión que usa el cliente de pruebas (un contexto anidado dejaría datos obsoletos en caché)
    db.session.get(Product, 1).stock = 2
    db.session.commit()
    res = client.get('/checkout/', follow_redirects=True)
    html = res.get_data(as_text=True)
    assert 'Martillo de Prueba' in html and 'pediste 5, hay 2' in html
    assert '/checkout/' not in res.request.path


def test_cart_update_of_missing_item_is_an_error_not_silent(client):
    res = client.post('/carrito/actualizar', json={'product_id': 1, 'quantity': 2})
    assert res.status_code == 400 and res.get_json()['success'] is False


def test_guest_cart_line_limit(app, client):
    from app.services.cart_service import CartService
    with app.app_context():
        for i in range(2, 2 + CartService.MAX_CART_LINES + 1):
            db.session.add(Product(category_id=1, sku=f'LIM-{i}', name=f'P{i}', slug=f'p{i}', price=Decimal('1'),
                                   stock=5, min_stock_alert=1, description='x', is_active=True))
        db.session.commit()
    codes = [client.post('/carrito/agregar', json={'product_id': pid, 'quantity': 1}).status_code
             for pid in range(2, 2 + CartService.MAX_CART_LINES + 1)]
    assert codes[:-1] == [200] * (len(codes) - 1) and codes[-1] == 400


def test_category_slug_collision_does_not_crash(app, client):
    _login(client, 'admin@ferreteria.com', 'AdminPass123*')
    assert client.post('/admin/categorias/crear', data={'name': 'Pintura', 'is_active': 'y'}).status_code == 302
    assert client.post('/admin/categorias/crear', data={'name': 'Pintura!', 'is_active': 'y'}).status_code == 302
    with app.app_context():
        slugs = sorted(c.slug for c in Category.query.filter(Category.name.in_(['Pintura', 'Pintura!'])).all())
        assert slugs == ['pintura', 'pintura-2']
        cid = Category.query.filter_by(name='Pintura').first().id
    # editar sin cambiar el nombre conserva su propio slug
    assert client.post(f'/admin/categorias/{cid}/editar', data={'name': 'Pintura', 'is_active': 'y'}).status_code == 302
    with app.app_context():
        assert db.session.get(Category, cid).slug == 'pintura'