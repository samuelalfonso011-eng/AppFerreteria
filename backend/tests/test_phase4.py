from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.models import Category, Order, OrderItem, OrderStatus, Product, User
from app.models.analytics import AnomalyAlert
from app.models.billing import Invoice
from app.services.statistics_service import boxplot, regression
from tests.conftest import CUSTOMER_PASSWORD
from tests.test_phase1 import employee_login

BASE = "/api/admin"


def sample_order(customer_id, product, index, quantity, price):
    day = datetime(2026, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=index)
    total = Decimal(price) * quantity
    order = Order(order_number=f"PH4-{index}", status=OrderStatus.CONFIRMED, subtotal=total, shipping_cost=0,
                  total=total, customer_id=customer_id, customer_name="Ana Pérez", customer_email="ana@test.com",
                  customer_phone="3001234567", doc_type="CC", doc_number="123456", department="Antioquia",
                  city="Medellín", neighborhood="Centro", street_address="Calle 10", policy_version="test",
                  terms_accepted_at=day, privacy_accepted_at=day, created_at=day)
    order.items.append(OrderItem(product_id=product.id, quantity=quantity, product_name=product.name,
                                 product_sku=product.sku, unit_price=price, subtotal=total))
    db.session.add(order)
    db.session.flush()
    return order


def test_audit_normalizes_and_keeps_ambiguous_records(admin_api):
    assert admin_api.get(BASE + "/data-quality/latest").get_json() is None
    p1, p2 = Product.query.order_by(Product.id).limit(2).all()
    p1.name, p2.name = "Broca", "BROCA"
    category = db.session.get(Category, p1.category_id)
    category.name = "  ELÉCTRICAS   DE   MANO "
    p1.price = 0
    db.session.commit()
    response = admin_api.post(BASE + "/data-quality/audit")
    assert response.status_code == 200
    report = response.get_json()
    assert report == admin_api.get(BASE + "/data-quality/latest").get_json()
    dup = [i for i in report["issues"] if i["module"] == "products" and i["issue_type"] == "duplicate_candidate"]
    assert {i["entity_id"] for i in dup} == {p1.id, p2.id}
    assert all(i["status"] == "pending_review" for i in dup)
    fix = next(i for i in report["issues"] if i["module"] == "categories" and i["entity_id"] == category.id)
    assert fix["original_value"] == "  ELÉCTRICAS   DE   MANO "
    assert fix["normalized_value"] == category.name == "Eléctricas de mano"
    assert fix["status"] == "auto_fixed"
    assert any(i["entity_id"] == p1.id and i["issue_type"] == "invalid_price" for i in report["issues"])
    assert admin_api.post(BASE + "/data-quality/audit").get_json()["auto_fixed_count"] == 0


def test_quartiles_profiles_and_source_ids(admin_api):
    customer = User.query.filter_by(role="customer").one()
    operator = User(full_name="Caja", email="cash@test.com", role="employee", password_hash="unused")
    db.session.add(operator)
    db.session.flush()
    product = Product.query.first()
    for i, amount in enumerate([10, 20, 30, 40, 1000]):
        order = sample_order(customer.id, product, i, 1, amount)
        discount = Decimal("800") if i == 4 else Decimal("0")
        invoice = Invoice(order_id=order.id, employee_id=operator.id, subtotal=amount, shipping_cost=0,
                          tax_amount=0, discount_amount=discount, total_amount=amount-discount)
        db.session.add(invoice)
    db.session.commit()
    assert boxplot([10, 20, 30, 40, 1000]) == {
        "n":5, "q1":20, "median":30, "q3":40, "iqr":20, "lower":-10, "upper":70,
        "whisker_min":10, "whisker_max":40, "outliers":[1000]}
    data = admin_api.get(BASE + "/analytics/users").get_json()
    alerts = {(a["user_role"],a["alert_type"]):a for a in data["alerts"]}
    high = alerts["customer","high_amount_outlier"]
    assert high["source_record_ids"] == {"order_ids":[order.id]}
    assert high["threshold_info"]["upper"] == 70 and 0 < high["anomaly_score"] <= 100
    assert alerts["employee","abusive_discounts"]["source_record_ids"] == {"invoice_ids":[invoice.id]}
    assert admin_api.get(BASE + "/analytics/users").get_json()["alerts"] == data["alerts"]
    assert AnomalyAlert.query.count() == len(data["alerts"])


def test_temporal_regression_holdout_and_demand(admin_api):
    # Primeros ocho valores = 2x + 1. El último par contiene errores +2 y -2.
    values = [1,3,5,7,9,11,13,15,19,17]
    result = regression(values,2)
    assert result["model"] == {"slope":2,"intercept":1}
    assert result["metrics"] == {"mae":2,"rmse":2,"r2":-3}
    assert result["estimates"][-2:] == [17,19]
    assert regression([3],1)["metrics"]["mae"] is None
    product = Product.query.first()
    for i, quantity in enumerate(values):
        sample_order(None, product, i, quantity, 100)
    db.session.commit()
    demand = admin_api.get(BASE+f"/analytics/demand?product_id={product.id}&horizon=2").get_json()
    assert [point["observed"] for point in demand["global"]["history"]] == values
    assert demand["products"][0]["metrics"] == result["metrics"]
    assert demand["global"]["forecast"][0]["period"] == "2026-01-11"
    weekly = admin_api.get(BASE+"/analytics/demand?period=weekly").get_json()["global"]
    assert weekly["short_series"] and weekly["history"][0]["period"] == "2025-12-29"
    assert admin_api.get(BASE+"/analytics/demand?period=month").status_code == 400


def test_quality_analytics_require_admin(api, app, admin_api):
    employee, _ = employee_login(app,admin_api)
    paths = [("post","/data-quality/audit"), ("get","/data-quality/latest"),
             ("get","/analytics/users"), ("get","/analytics/demand")]
    for method,path in paths:
        assert getattr(api,method)(BASE+path).status_code == 401
        assert getattr(employee,method)(BASE+path).status_code == 403
    api.login("cliente@ferrepro.test",CUSTOMER_PASSWORD)
    for method,path in paths:
        assert getattr(api,method)(BASE+path).status_code == 403


def test_duplicate_phone_and_malformed_historical_price(admin_api):
    from sqlalchemy import text

    product = Product.query.first()
    original = User.query.filter_by(role="customer").one()
    other = User(full_name="Otra cuenta", email="otra@example.test", role="customer", password_hash="unused")
    db.session.add(other)
    db.session.flush()
    sample_order(original.id, product, 0, 1, 150)
    sample_order(other.id, product, 1, 1, 150)
    # Una importación antigua de SQLite puede contener texto en una columna NUMERIC.
    db.session.execute(text("UPDATE products SET price='ilegible' WHERE id=:id"), {"id": product.id})
    product_id = product.id
    db.session.commit()
    response = admin_api.post(BASE+"/data-quality/audit")
    assert response.status_code == 200
    issues = response.get_json()["issues"]
    phone = [i for i in issues if i["module"] == "users" and i["details"]["field"] == "phone"]
    assert {i["entity_id"] for i in phone} == {original.id, other.id}
    assert all(i["status"] == "pending_review" for i in phone)
    assert any(i["module"] == "products" and i["entity_id"] == product_id and
               i["issue_type"] == "invalid_price" and i["original_value"] == "ilegible" for i in issues)
