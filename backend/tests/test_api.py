import uuid

from app.extensions import db
from app.models import InventoryMovement, Order, OrderStatus, PrivacyConsent, Product
from tests.conftest import CUSTOMER_PASSWORD


def checkout_payload(items, **overrides):
    payload = {
        "name": "Laura Gómez",
        "email": "laura@example.com",
        "phone": "3001234567",
        "doc_type": "CC",
        "doc_number": "1020304050",
        "department": "Antioquia",
        "city": "Medellín",
        "neighborhood": "Laureles",
        "street_address": "Carrera 70 # 44-10",
        "accept_terms": True,
        "accept_privacy": True,
        "items": items,
        "idempotency_key": str(uuid.uuid4()),
    }
    payload.update(overrides)
    return payload


def product_by_sku(sku):
    return Product.query.filter_by(sku=sku).first()


# ---------------------------------------------------------------- catalogo y cache

def test_catalog_lists_seeded_products(api):
    response = api.get("/api/catalog/products")
    assert response.status_code == 200
    names = [p["name"] for p in response.get_json()["products"]]
    assert "Taladro Percutor Pro X1" in names and len(names) == 6
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers.get("ETag")


def test_etag_returns_304_when_unchanged(api):
    first = api.get("/api/catalog/products")
    etag = first.headers["ETag"]
    second = api.get("/api/catalog/products", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.headers["X-Cache"] == "HIT"


def test_admin_price_change_invalidates_catalog(api, admin_api, app):
    before = api.get("/api/catalog/products")
    with app.app_context():
        product = product_by_sku("FP-0003")
        body = product.to_admin()
    body.update({"price": 99900, "is_active": True})
    assert admin_api.put(f"/api/admin/products/{body['id']}", body).status_code == 200

    after = api.get("/api/catalog/products", headers={"If-None-Match": before.headers["ETag"]})
    assert after.status_code == 200, "el ETag anterior ya no debe ser valido"
    prices = {p["sku"]: p["price"] for p in after.get_json()["products"]}
    assert prices["FP-0003"] == 99900


def test_deactivated_product_disappears_immediately(api, admin_api, app):
    api.get("/api/catalog/products")  # llena la cache
    with app.app_context():
        pid = product_by_sku("FP-0006").id
    assert admin_api.post(f"/api/admin/products/{pid}/toggle").status_code == 200
    skus = [p["sku"] for p in api.get("/api/catalog/products").get_json()["products"]]
    assert "FP-0006" not in skus


# ---------------------------------------------------------------- checkout y legal

def test_checkout_requires_legal_acceptance(api, app):
    with app.app_context():
        pid = product_by_sku("FP-0001").id
    response = api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}],
                                                        accept_terms=False, accept_privacy=False))
    assert response.status_code == 400
    fields = response.get_json()["fields"]
    assert "accept_terms" in fields and "accept_privacy" in fields


def test_checkout_creates_order_deducts_stock_and_records_consent(api, app):
    with app.app_context():
        product = product_by_sku("FP-0001")
        pid, stock = product.id, product.stock
    api.get("/api/catalog/products")  # cache caliente antes de comprar
    response = api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 2}]))
    assert response.status_code == 201
    order = response.get_json()["order"]
    assert order["status"] == OrderStatus.PENDING
    assert order["total"] == 489900 * 2  # supera el umbral: envio gratis

    catalog = {p["id"]: p for p in api.get("/api/catalog/products").get_json()["products"]}
    assert catalog[pid]["stock"] == stock - 2, "la compra debe invalidar el stock cacheado"

    with app.app_context():
        saved = Order.query.filter_by(order_number=order["order_number"]).one()
        assert saved.terms_accepted_at and saved.privacy_accepted_at and saved.policy_version
        docs = {c.document for c in PrivacyConsent.query.filter_by(order_id=saved.id)}
        assert docs == {"terms", "habeas_data"}
        assert InventoryMovement.query.filter_by(reference=saved.order_number).count() == 1


def test_checkout_is_idempotent(api, app):
    with app.app_context():
        pid = product_by_sku("FP-0004").id
    payload = checkout_payload([{"product_id": pid, "quantity": 1}])
    first = api.post("/api/orders", payload)
    second = api.post("/api/orders", payload)
    assert first.status_code == 201 and second.status_code == 200
    assert first.get_json()["order"]["order_number"] == second.get_json()["order"]["order_number"]


def test_checkout_rejects_insufficient_stock(api, app):
    with app.app_context():
        product = product_by_sku("FP-0005")
        pid, stock = product.id, product.stock
    response = api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": stock + 1}]))
    assert response.status_code == 409
    assert response.get_json()["error"] == "stock"
    with app.app_context():
        assert product_by_sku("FP-0005").stock == stock


def test_checkout_detects_price_change(api, app):
    with app.app_context():
        pid = product_by_sku("FP-0004").id
    response = api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}], expected_total=1))
    assert response.status_code == 409
    assert response.get_json()["error"] == "price_changed"


def test_order_lookup_requires_matching_email(api, app):
    with app.app_context():
        pid = product_by_sku("FP-0004").id
    number = api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}])).get_json()["order"]["order_number"]
    ok = api.post("/api/orders/lookup", {"order_number": number, "email": "laura@example.com"})
    wrong = api.post("/api/orders/lookup", {"order_number": number, "email": "otra@example.com"})
    assert ok.status_code == 200 and wrong.status_code == 404


def test_legal_documents_are_served(api):
    for slug in ("privacidad", "datos", "terminos", "devoluciones", "cookies"):
        response = api.get(f"/api/legal/{slug}")
        assert response.status_code == 200
        assert response.get_json()["document"]["sections"]
    assert api.get("/api/legal/inexistente").status_code == 404


# ---------------------------------------------------------------- seguridad

def test_writes_require_csrf(api, app):
    with app.app_context():
        pid = product_by_sku("FP-0001").id
    response = api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}]), csrf=False)
    assert response.status_code == 403
    assert response.get_json()["error"] == "csrf"


def test_admin_routes_require_admin(api):
    assert api.get("/api/admin/dashboard").status_code == 401
    assert api.login("cliente@ferrepro.test", CUSTOMER_PASSWORD).status_code == 200
    assert api.get("/api/admin/dashboard").status_code == 403
    assert api.get("/api/admin/orders").status_code == 403


def test_login_rejects_bad_password_and_rate_limits(api):
    for _ in range(5):
        assert api.login("admin@ferrepro.test", "incorrecta123").status_code == 401
    assert api.login("admin@ferrepro.test", "incorrecta123").status_code == 429


def test_backend_files_are_not_served(api):
    assert api.get("/backend/app/config.py").status_code == 404
    assert api.get("/backend/.env").status_code == 404
    assert api.get("/AGENTS.md").status_code == 404
    assert api.get("/").status_code == 200


# ---------------------------------------------------------------- admin

def test_admin_cancel_restores_stock(api, admin_api, app):
    with app.app_context():
        product = product_by_sku("FP-0002")
        pid, stock = product.id, product.stock
    number = api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 3}])).get_json()["order"]["order_number"]
    with app.app_context():
        order_id = Order.query.filter_by(order_number=number).one().id
        assert db.session.get(Product, pid).stock == stock - 3

    response = admin_api.post(f"/api/admin/orders/{order_id}/status", {"status": OrderStatus.CANCELLED,
                                                                        "comment": "Cliente desistió"})
    assert response.status_code == 200
    again = admin_api.post(f"/api/admin/orders/{order_id}/status", {"status": OrderStatus.CANCELLED})
    assert again.status_code == 409, "un pedido cancelado no se cancela dos veces"
    with app.app_context():
        assert db.session.get(Product, pid).stock == stock


def test_admin_invalid_transition_is_rejected(api, admin_api, app):
    with app.app_context():
        pid = product_by_sku("FP-0003").id
    number = api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}])).get_json()["order"]["order_number"]
    with app.app_context():
        order_id = Order.query.filter_by(order_number=number).one().id
    response = admin_api.post(f"/api/admin/orders/{order_id}/status", {"status": OrderStatus.DELIVERED})
    assert response.status_code == 409


def test_admin_dashboard_reflects_confirmed_sale(api, admin_api, app):
    with app.app_context():
        pid = product_by_sku("FP-0004").id
    assert admin_api.get("/api/admin/dashboard").get_json()["sales"]["month"] == 0
    number = api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}])).get_json()["order"]["order_number"]
    with app.app_context():
        order_id = Order.query.filter_by(order_number=number).one().id
    admin_api.post(f"/api/admin/orders/{order_id}/status", {"status": OrderStatus.CONFIRMED})
    month = admin_api.get("/api/admin/dashboard").get_json()["sales"]["month"]
    assert month == 24900 + 15000


def test_admin_inventory_adjustment_and_kardex(admin_api, app):
    with app.app_context():
        product = product_by_sku("FP-0005")
        pid, stock = product.id, product.stock
    response = admin_api.post(f"/api/admin/inventory/{pid}/adjust",
                              {"movement_type": "PURCHASE_ENTRY", "quantity": 10, "reason": "Compra a proveedor"})
    assert response.status_code == 200
    assert response.get_json()["product"]["stock"] == stock + 10
    too_much = admin_api.post(f"/api/admin/inventory/{pid}/adjust",
                              {"movement_type": "ADJUSTMENT_OUT", "quantity": 999, "reason": "Prueba de faltante"})
    assert too_much.status_code == 409
    kardex = admin_api.get(f"/api/admin/inventory/{pid}/movements").get_json()["movements"]
    assert kardex[0]["type"] == "PURCHASE_ENTRY"


def test_admin_cannot_delete_product_with_orders(api, admin_api, app):
    with app.app_context():
        pid = product_by_sku("FP-0004").id
    api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}]))
    assert admin_api.delete(f"/api/admin/products/{pid}").status_code == 409


def test_admin_create_product_validates_input(admin_api):
    bad = admin_api.post("/api/admin/products", {"name": "x", "price": -5})
    assert bad.status_code == 400
    fields = bad.get_json()["fields"]
    assert {"name", "sku", "category_id", "price"} <= set(fields)
