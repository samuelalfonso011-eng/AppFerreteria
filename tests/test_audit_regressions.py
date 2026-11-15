"""Regresiones de la auditoría integral: coste SQL, transacciones y controles web."""
from contextlib import contextmanager
from decimal import Decimal

import pytest
from flask import session
from sqlalchemy import event

from app.extensions import db
from app.models.cart import Cart, CartItem
from app.models.category import Category, generate_unique_slug
from app.models.product import Product
from app.models.user import User
from app.services.cart_service import CartService
from app.services.inventory_service import InventoryService, InsufficientStockError


@contextmanager
def select_queries():
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)


def add_products(count):
    products = [Product(category_id=1, sku=f"AUDIT-{i}", name=f"Producto {i}",
                        slug=f"audit-{i}", price=Decimal("100"), stock=10)
                for i in range(count)]
    db.session.add_all(products)
    db.session.flush()
    ids = [p.id for p in products]
    db.session.commit()
    return ids


def test_inventory_batch_reads_and_duplicate_quantities(app):
    with app.app_context():
        ids = add_products(12)
        with select_queries() as queries:
            InventoryService.deduct_stock_for_order(
                [{"product_id": pid, "quantity": 1} for pid in ids], 1, "AUDIT")
        assert len(queries) == 1
        db.session.rollback()
        with pytest.raises(InsufficientStockError):
            InventoryService.deduct_stock_for_order(
                [{"product_id": ids[0], "quantity": 6}] * 2, 1, "DUPLICATE")
        assert db.session.get(Product, ids[0]).stock == 10


def test_guest_cart_sync_uses_bounded_queries(app):
    with app.test_request_context():
        ids = add_products(12)
        user = db.session.get(User, 2)
        CartService._get_or_create_user_cart(user.id)
        session[CartService.SESSION_KEY] = {str(pid): 2 for pid in ids}
        with select_queries() as queries:
            CartService.sync_guest_cart_to_user(user)
        assert len(queries) <= 3
        with select_queries() as queries:
            data = CartService.get_cart_data(user)
        assert data["total_items"] == 24
        assert len(queries) <= 2


def test_slug_collision_search_is_one_query(app):
    with app.app_context():
        db.session.add_all([Category(name=f"Cat {i}", slug=f"collision-{i}") for i in range(2, 20)])
        db.session.add(Category(name="Cat base", slug="collision"))
        db.session.commit()
        with select_queries() as queries:
            assert generate_unique_slug("collision", Category) == "collision-20"
        assert len(queries) == 1


def _count_queries(statements, table):
    return [s for s in statements if "count(" in s.lower() and table in s.lower()]


def test_listing_counts_use_one_grouped_query(app, client):
    import re
    with app.app_context():
        add_products(11)  # 1 del fixture + 11 = 12 activos en "Herramientas"
        db.session.add(Product(category_id=1, sku="AUDIT-OFF", name="Inactivo",
                               slug="audit-off", price=Decimal("100"), stock=1,
                               is_active=False))
        for i in range(4):
            cat = Category(name=f"Extra {i}", slug=f"extra-{i}", is_active=True)
            db.session.add(cat)
            db.session.flush()
            db.session.add(Product(category_id=cat.id, sku=f"EX-{i}", name=f"Extra {i}",
                                   slug=f"extra-prod-{i}", price=Decimal("1"), stock=1))
        db.session.commit()

        # Público: solo productos activos, una consulta agrupada para todas las categorías
        with select_queries() as queries:
            html = client.get("/").get_data(as_text=True)
        counts = re.findall(r'cat-chip-count">\s*(\d+)', html)
        assert "12" in counts and counts.count("1") == 4
        assert len(_count_queries(queries, "products")) == 1

        # Admin: total incluyendo inactivos, una consulta agrupada
        login(client, "admin@ferreteria.com", "AdminPass123*")
        with select_queries() as queries:
            html = client.get("/admin/categorias/").get_data(as_text=True)
        assert re.search(r'badge-info">\s*13\s*<', html)
        assert len(_count_queries(queries, "products")) == 1

        # Clientes: un conteo agrupado de pedidos para la página actual
        with select_queries() as queries:
            assert client.get("/admin/clientes/").status_code == 200
        assert len(_count_queries(queries, "orders")) == 1


def test_order_failure_rolls_back_stock_and_cart_together(app, monkeypatch):
    from app.services.order_service import OrderService
    from app.models.order import Order
    with app.app_context():
        user = db.session.get(User, 2)
        CartService.add_item(1, 2, user)
        def fail_commit():
            raise RuntimeError("database unavailable")
        monkeypatch.setattr(db.session, "commit", fail_commit)
        with pytest.raises(RuntimeError):
            OrderService.create_order(user, {"recipient_name": "Juan", "phone": "300",
                "city": "Medellín", "neighborhood": "Centro", "street_address": "Calle 1"})
        assert db.session.get(Product, 1).stock == 10
        assert Order.query.count() == 0
        assert CartService.get_cart_data(user)["total_items"] == 2


def test_cache_isolation_and_commit_boundary(app):
    from app import create_app
    from app.utils.cache import cache
    with app.app_context():
        cache.set("products:example", "first")
        product = db.session.get(Product, 1)
        product.name = "Changed"
        db.session.flush()
        assert cache.get("products:example") == "first"
        db.session.commit()
        assert cache.get("products:example") is None
        cache.set("products:example", "first")
        other = create_app("testing")
        with other.app_context():
            assert cache.get("products:example") is None
            cache.set("products:example", "second")
        assert cache.get("products:example") == "first"


def test_cart_handles_legacy_malformed_session(app):
    with app.test_request_context():
        for raw in ([], None, {"1": "two"}, {"1": True}, {"1": -3}):
            session[CartService.SESSION_KEY] = raw
            assert CartService.get_cart_data()["total_items"] == 0


def test_stock_can_be_adjusted_to_zero(app):
    from app.forms.admin_forms import StockAdjustmentForm
    from werkzeug.datastructures import MultiDict
    with app.test_request_context():
        form = StockAdjustmentForm(MultiDict({"target_stock": "0", "reason": "Recuento"}))
        assert form.validate()



def login(client, email="cliente@correo.com", password="ClientePass123*"):
    return client.post('/login', data={"email": email, "password": password})


@pytest.mark.parametrize("value", [True, 1.5, "1.2", [], {}, -1, 2147483648])
def test_cart_rejects_non_integer_quantities(client, value):
    response = client.post('/carrito/agregar', json={"product_id": 1, "quantity": value})
    assert response.status_code == 400


def test_disabled_user_and_changed_password_revoke_sessions(app, client):
    login(client)
    with app.app_context():
        user = db.session.get(User, 2)
        user.is_active = False
        db.session.commit()
    # El fixture mantiene un app_context abierto; simular el contexto nuevo de una petición real.
    from flask import g
    g.pop('_login_user', None)
    db.session.expire_all()
    assert client.get('/perfil').status_code == 302
    with app.app_context():
        user = db.session.get(User, 2)
        user.is_active = True
        db.session.commit()
    login(client)
    with app.app_context():
        db.session.get(User, 2).set_password('ChangedPassword123!')
        db.session.commit()
    # El fixture mantiene un app_context abierto; simular el contexto nuevo de una petición real.
    from flask import g
    g.pop('_login_user', None)
    db.session.expire_all()
    assert client.get('/perfil').status_code == 302


def test_untrusted_proxy_cannot_bypass_ip_limit(app, client):
    from app.utils.anti_spam import reset_rate_limits
    reset_rate_limits()
    app.config['ENFORCE_RATE_LIMIT'] = True
    for i in range(21):
        response = client.post('/login', data={"email": f"u{i}@example.com", "password": "bad"},
                               headers={"X-Forwarded-For": f"192.0.2.{i}"})
    assert response.status_code == 429
    reset_rate_limits()


def test_csrf_is_enforced_for_json_mutations(app, client):
    app.config['WTF_CSRF_ENABLED'] = True
    response = client.post('/carrito/agregar', json={"product_id": 1, "quantity": 1})
    assert response.status_code == 400
    assert response.json['success'] is False


def test_idempotency_key_is_scoped_to_owner(app):
    from app.services.order_service import OrderService
    with app.app_context():
        shipping = {"recipient_name": "Juan", "phone": "300", "city": "Medellín",
                    "neighborhood": "Centro", "street_address": "Calle 1"}
        customer = db.session.get(User, 2)
        CartService.add_item(1, 1, customer)
        OrderService.create_order(customer, shipping, idempotency_key='owner-key')
        with pytest.raises(ValueError):
            OrderService.create_order(db.session.get(User, 1), shipping, idempotency_key='owner-key')


def test_legacy_demo_account_can_be_revoked(app, runner):
    with app.app_context():
        user = User(email='sistema@ferreteria.local', full_name='Legacy', role_id=1, is_active=True)
        user.set_password('OldPassword123!')
        db.session.add(user)
        db.session.commit()
    assert runner.invoke(args=['disable-legacy-demo-account']).exit_code == 0
    with app.app_context():
        user = User.query.filter_by(email='sistema@ferreteria.local').one()
        assert not user.is_active
        assert not user.check_password('OldPassword123!')


def test_sensitive_html_is_not_cacheable(client):
    login(client)
    assert client.get('/perfil').headers['Cache-Control'] == 'no-store'


def test_registration_requires_explicit_consent_and_records_it(app, client):
    from app.models.consent import PrivacyConsent, POLICY_VERSION
    payload = dict(full_name='Nuevo Usuario', email='new@example.com', password='SecurePassword123!',
                   confirm_password='SecurePassword123!', accept_terms='y')
    assert client.post('/registro', data=payload).status_code == 200
    assert User.query.filter_by(email='new@example.com').first() is None
    payload['accept_privacy'] = 'y'
    assert client.post('/registro', data=payload).status_code == 302
    consent = PrivacyConsent.query.filter_by(purpose='registration').one()
    assert consent.policy_version == POLICY_VERSION and consent.accepted_at
    assert consent.user_id == User.query.filter_by(email='new@example.com').one().id


def test_contact_requires_server_side_consent(app, client):
    from app.models.contact import ContactMessage
    from app.models.consent import PrivacyConsent
    payload = dict(full_name='Usuario Prueba', email='contact@example.com', subject='otro',
                   message='Quisiera consultar sobre un producto disponible.')
    client.post('/contacto', data=payload)
    assert ContactMessage.query.count() == 0
    payload['accept_privacy'] = 'y'
    assert client.post('/contacto', data=payload).status_code == 302
    assert PrivacyConsent.query.filter_by(purpose='contact').count() == 1
    html = client.get('/contacto').get_data(as_text=True)
    assert 'name="form_token"' in html


def test_checkout_requires_consent_before_stock_changes(app, client):
    from app.models.order import Order
    from app.models.consent import PrivacyConsent
    login(client)
    client.post('/carrito/agregar', json=dict(product_id=1, quantity=1))
    payload = dict(saved_address_id='0', recipient_name='Juan Perez', phone='3001234567',
                   city='Medellín', neighborhood='Centro', street_address='Calle 1',
                   idempotency_key='consent-order')
    client.post('/checkout/', data=payload)
    assert Order.query.count() == 0
    assert db.session.get(Product, 1).stock == 10
    payload['accept_privacy'] = 'y'
    assert client.post('/checkout/', data=payload).status_code == 302
    consent = PrivacyConsent.query.filter_by(purpose='checkout').one()
    assert consent.order_id == Order.query.one().id


@pytest.mark.parametrize('path', ['/registro', '/contacto', '/tratamiento-de-datos', '/politica-de-cookies'])
def test_privacy_pages_and_unchecked_authorizations(client, path):
    import re
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'cookiePreferences' in html
    assert 'fonts.googleapis.com' not in html
    for tag in re.findall(r'<input[^>]+>', html):
        if 'name="accept_privacy"' in tag or 'name="accept_terms"' in tag:
            assert 'checked' not in tag
