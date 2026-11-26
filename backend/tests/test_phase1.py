import base64
from decimal import Decimal
from io import BytesIO

from app.extensions import db
from app.models import InventoryMovement, Order, Product, User
from app.models.billing import Invoice, Payment
from tests.conftest import ApiClient, CUSTOMER_PASSWORD
from tests.test_api import checkout_payload

EMPLOYEE_EMAIL = "caja@ferrepro.test"
EMPLOYEE_PASSWORD = "TurnoSeguro2026"
RECEIPT = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jv7sAAAAASUVORK5CYII="
)


def employee_login(app, admin_api):
    response = admin_api.post("/api/admin/users", {
        "name": "Turno de caja", "email": EMPLOYEE_EMAIL,
        "password": EMPLOYEE_PASSWORD, "role": "employee",
    })
    assert response.status_code == 201
    account = response.get_json()["user"]
    assert "password_hash" not in account
    employee = ApiClient(app.test_client())
    assert employee.login(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD).status_code == 200
    return employee, account["id"]


def test_sale_invoice_retry_and_private_payment(app, api, admin_api):
    app.config["INVOICE_TAX_RATE"] = Decimal("0.19")
    employee, employee_id = employee_login(app, admin_api)
    products = Product.query.order_by(Product.id).limit(2).all()
    stock = {product.id: product.stock for product in products}
    customer_id = User.by_email("cliente@ferrepro.test").id
    items = [{"product_id": product.id, "quantity": index + 1}
             for index, product in enumerate(products)]
    payload = checkout_payload(items, channel="presencial", customer_id=customer_id)
    for field in ("department", "city", "neighborhood", "street_address"):
        payload.pop(field)
    response = employee.post("/api/orders", payload)
    assert response.status_code == 201
    order = response.get_json()["order"]
    assert (order["channel"], order["customer_id"], order["employee_id"]) == (
        "presencial", customer_id, employee_id,
    )
    assert order["shipping_cost"] == 0
    assert employee.post("/api/orders", payload).status_code == 200
    for line in items:
        product_id = line["product_id"]
        assert db.session.get(Product, product_id).stock == stock[product_id] - line["quantity"]

    staff_list = employee.get("/api/staff/orders?channel=presencial").get_json()
    assert [row["id"] for row in staff_list["orders"]] == [order["id"]]
    assert staff_list["orders"][0]["employee_name"] == "Turno de caja"
    assert employee.get(f"/api/staff/orders/{order['id']}").get_json()["order"]["allowed_transitions"] == []
    assert admin_api.get(f"/api/staff/orders/{order['id']}").status_code == 404
    assert api.get("/api/staff/orders").status_code == 401
    assert employee.get("/api/admin/orders").status_code == 403
    accounts = admin_api.get("/api/admin/users?role=employee&q=caja").get_json()
    assert [user["id"] for user in accounts["users"]] == [employee_id]

    invoice_url = f"/api/orders/{order['id']}/invoice"
    assert api.post(invoice_url).status_code == 401
    assert api.get(invoice_url).status_code == 401
    empty = employee.get(invoice_url)
    assert empty.status_code == 200
    assert empty.get_json() == {"invoice": None, "payments": [], "balance": 0}
    assert admin_api.get("/api/orders/2147483647/invoice").status_code == 404
    response = employee.post(invoice_url, {"discount_amount": "1000.05"})
    assert response.status_code == 201
    invoice = response.get_json()["invoice"]
    subtotal = Decimal(invoice["subtotal"])
    discount = Decimal("1000.05")
    tax = ((subtotal - discount) * Decimal("0.19")).quantize(Decimal("0.01"))
    assert Decimal(invoice["tax_amount"]) == tax
    assert Decimal(invoice["discount_amount"]) == discount
    assert Decimal(invoice["total_amount"]) == subtotal - discount + tax + Decimal(invoice["shipping_cost"])
    assert invoice["invoice_number"] > 0 and len(invoice["items"]) == 2

    retry = employee.post(invoice_url, {"discount_amount": "0.00"})
    assert retry.status_code == 200
    assert retry.get_json() == {"invoice": invoice, "created": False}
    assert Invoice.query.filter_by(order_id=order["id"]).count() == 1
    assert InventoryMovement.query.filter_by(reference=order["order_number"], user_id=employee_id).count() == 2
    for line in items:
        product_id = line["product_id"]
        assert db.session.get(Product, product_id).stock == stock[product_id] - line["quantity"]

    other_order = employee.post("/api/orders", checkout_payload(items, channel="domicilio")).get_json()["order"]
    next_invoice = employee.post(f"/api/orders/{other_order['id']}/invoice").get_json()["invoice"]
    assert next_invoice["invoice_number"] == invoice["invoice_number"] + 1

    payment_url = f"/api/invoices/{invoice['id']}/payments"

    def upload(data, mime="image/png", csrf=True):
        return employee.client.post(
            payment_url,
            data={"payment_method": "transferencia", "amount": "10000.00",
                  "receipt": (BytesIO(data), "comprobante.png", mime)},
            headers={"X-CSRF-Token": employee.token()} if csrf else {},
        )

    assert upload(RECEIPT, csrf=False).status_code == 403
    assert upload(b"not an image").status_code == 400
    assert upload(b"a" * (5 * 1024 * 1024 + 1)).status_code == 413
    response = upload(RECEIPT)
    assert response.status_code == 201
    payment = response.get_json()["payment"]
    assert payment["status"] == "pendiente" and payment["paid_at"] is None
    assert payment["invoice_id"] == invoice["id"] and payment["order_id"] == order["id"]
    assert Payment.query.count() == 1
    assert api.get(payment["receipt_url"]).status_code == 401
    assert api.login("cliente@ferrepro.test", CUSTOMER_PASSWORD).status_code == 200
    assert api.get(payment["receipt_url"]).status_code == 403
    receipt = employee.get(payment["receipt_url"])
    assert receipt.data == RECEIPT and receipt.mimetype == "image/png"
    assert receipt.headers["Content-Disposition"].startswith("attachment;")
    assert receipt.headers["Cache-Control"] == "private, no-store"
    assert admin_api.get(payment["receipt_url"]).status_code == 200
    assert employee.post(payment_url, {"payment_method": "efectivo",
                                       "amount": invoice["total_amount"]}).status_code == 409
    approved = employee.post(payment_url, {"payment_method": "efectivo", "amount": "2500.15"})
    assert approved.status_code == 201
    details = admin_api.get(invoice_url)
    assert details.status_code == 200
    body = details.get_json()
    assert body["invoice"] == invoice
    assert body["payments"] == [payment, approved.get_json()["payment"]]
    assert Decimal(str(body["balance"])) == Decimal(invoice["total_amount"]) - Decimal("2500.15")
    assert api.get(invoice_url).status_code == 403


def test_admin_orders_filter_by_channel(app, admin_api):
    product = Product.query.first()
    items = [{"product_id": product.id, "quantity": 1}]
    for channel in ("presencial", "web", "app", "domicilio"):
        assert admin_api.post("/api/orders", checkout_payload(items, channel=channel)).status_code == 201

    unfiltered = admin_api.get("/api/admin/orders").get_json()
    assert unfiltered["total"] == 4
    for channel in ("presencial", "web", "app", "domicilio"):
        response = admin_api.get(f"/api/admin/orders?channel={channel}")
        assert response.status_code == 200
        body = response.get_json()
        assert body["total"] == 1
        assert [order["channel"] for order in body["orders"]] == [channel]

    for channel in ("", "otro"):
        response = admin_api.get(f"/api/admin/orders?channel={channel}")
        assert response.status_code == 400
        assert "channel" in response.get_json()["fields"]


def test_user_permissions_session_revocation_and_customer_link(app, api, admin_api):
    employee, user_id = employee_login(app, admin_api)
    product = Product.query.first()
    items = [{"product_id": product.id, "quantity": 1}]
    assert employee.get("/api/admin/users").status_code == 403
    assert api.post("/api/orders", checkout_payload(items, channel="presencial")).status_code == 403
    assert api.login("cliente@ferrepro.test", CUSTOMER_PASSWORD).status_code == 200
    response = api.post("/api/orders", checkout_payload(items, channel="app"))
    assert response.status_code == 201
    order = Order.query.filter_by(order_number=response.get_json()["order"]["order_number"]).one()
    assert order.customer_id == User.by_email("cliente@ferrepro.test").id and order.employee_id is None
    assert employee.post(f"/api/orders/{order.id}/invoice").status_code == 404
    assert employee.get(f"/api/orders/{order.id}/invoice").status_code == 404

    users = admin_api.get("/api/admin/users").get_json()["users"]
    assert any(user["id"] == user_id and user["role"] == "employee" for user in users)
    url = f"/api/admin/users/{user_id}"
    assert admin_api.send("PATCH", url, {"is_active": False}).get_json()["user"]["is_active"] is False
    assert employee.get("/api/auth/me").get_json()["user"] is None
    assert employee.login(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD).status_code == 401
    updated = admin_api.send("PATCH", url, {"role": "customer", "is_active": True}).get_json()["user"]
    assert updated["role"] == "customer" and updated["is_active"]
    assert employee.login(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD).status_code == 200
    assert employee.post(f"/api/orders/{order.id}/invoice").status_code == 403
