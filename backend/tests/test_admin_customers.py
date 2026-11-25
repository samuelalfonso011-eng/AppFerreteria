
from app.extensions import db
from app.models import Product, User, record_consent
from tests.conftest import CUSTOMER_PASSWORD
from tests.test_api import checkout_payload

ALLOWED_FIELDS = {"id", "name", "email", "status", "created_at", "last_login_at", "orders", "habeas_data"}


def add_pending_customer(app, email="pendiente@example.com", name="Pedro Pendiente"):
    with app.app_context():
        user = User(email=email, full_name=name, role=User.ROLE_CUSTOMER, is_active=False,
                    email_verification_pending=True)
        user.set_password("PendienteSeguro2026")
        db.session.add(user)
        db.session.flush()
        record_consent("registration", "habeas_data", user_id=user.id, ip_address="203.0.113.7")
        record_consent("registration", "terms", user_id=user.id, ip_address="203.0.113.7")
        db.session.commit()


def test_customers_requires_admin(api):
    assert api.get("/api/admin/customers").status_code == 401
    assert api.login("cliente@ferrepro.test", CUSTOMER_PASSWORD).status_code == 200
    assert api.get("/api/admin/customers").status_code == 403


def test_customers_lists_only_customers_with_whitelisted_fields(admin_api, app):
    add_pending_customer(app)
    response = admin_api.get("/api/admin/customers")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.get_json()
    emails = {c["email"] for c in data["customers"]}
    assert emails == {"cliente@ferrepro.test", "pendiente@example.com"}  # el admin no aparece
    for customer in data["customers"]:
        assert set(customer) == ALLOWED_FIELDS
    raw = response.get_data(as_text=True).lower()
    for secret in ("password", "hash", "scrypt", "pbkdf2", "token", "session", "203.0.113.7", "ip_address"):
        assert secret not in raw, secret


def test_customers_status_and_filters(admin_api, app):
    add_pending_customer(app)
    data = admin_api.get("/api/admin/customers").get_json()
    status = {c["email"]: c["status"] for c in data["customers"]}
    assert status == {"cliente@ferrepro.test": "verified", "pendiente@example.com": "pending"}
    assert data["counts"] == {"all": 2, "verified": 1, "pending": 1}

    verified = admin_api.get("/api/admin/customers?status=verified").get_json()["customers"]
    pending = admin_api.get("/api/admin/customers?status=pending").get_json()["customers"]
    assert [c["email"] for c in verified] == ["cliente@ferrepro.test"]
    assert [c["email"] for c in pending] == ["pendiente@example.com"]
    # Un filtro desconocido equivale a "todos"
    assert admin_api.get("/api/admin/customers?status=hackeo").get_json()["total"] == 2


def test_customers_search_by_name_or_email(admin_api, app):
    add_pending_customer(app)
    by_name = admin_api.get("/api/admin/customers?q=pedro").get_json()["customers"]
    by_email = admin_api.get("/api/admin/customers?q=CLIENTE@ferre").get_json()["customers"]
    wildcard = admin_api.get("/api/admin/customers?q=%25").get_json()["customers"]
    assert [c["email"] for c in by_name] == ["pendiente@example.com"]
    assert [c["email"] for c in by_email] == ["cliente@ferrepro.test"]
    assert wildcard == []  # el % se busca literal, no como comodin


def test_customers_orders_and_habeas_data(admin_api, api, app):
    add_pending_customer(app)
    with app.app_context():
        pid = Product.query.filter_by(sku="FP-0004").first().id
    for _ in range(2):
        api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}], email="Cliente@Ferrepro.test"))
    data = {c["email"]: c for c in admin_api.get("/api/admin/customers").get_json()["customers"]}
    assert data["cliente@ferrepro.test"]["orders"] == 2  # sin importar mayusculas en el correo del pedido
    assert data["pendiente@example.com"]["orders"] == 0
    assert data["pendiente@example.com"]["habeas_data"]["accepted"] is True
    assert data["pendiente@example.com"]["habeas_data"]["policy_version"]
    assert data["cliente@ferrepro.test"]["habeas_data"] == {"accepted": False, "accepted_at": None, "policy_version": None}


def test_customers_endpoint_is_read_only(admin_api):
    for method in ("post", "put", "delete"):
        response = getattr(admin_api, method)("/api/admin/customers")
        assert response.status_code == 405, method
