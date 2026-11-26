from datetime import date, datetime, timedelta, timezone

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.ml import data_pipeline as pipeline
from app.models import Product, User
from app.models.ml import FraudPrediction, ModelRun
from tests.conftest import ADMIN_PASSWORD, ApiClient, CUSTOMER_PASSWORD
from tests.test_phase1 import employee_login

ROOT = "/api/admin/ml"
TRANSACTION = {
    "transaction": {
        "occurred_at": "2025-01-01T15:00:00Z",
        "amount": 50000,
        "channel": "web",
        "payment_method": "tarjeta",
        "prior_frequency": 3,
        "hash_valid": 1,
    }
}


def test_time_split_and_simulation(app):
    first = datetime(2025, 1, 1, tzinfo=timezone.utc)
    dates = [first + timedelta(days=i // 2) for i in range(20)]
    cut = pipeline.split_time(dates)
    assert cut == first + timedelta(days=8)
    train, test, summary = pipeline.fraud_dataset(42)
    assert max(r[0] for r in train) < min(r[0] for r in test)
    assert all(r[3] == "simulated" for r in train + test)
    assert pipeline.fraud_dataset(42) == (train, test, summary)
    assert pipeline.demand_vector(date(2025, 1, 1), [1, 2, 3])[:3] == [3, 2, 3]


def test_train_reload_and_persist(tmp_path, monkeypatch):
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", "sqlite:///" + str(tmp_path / "ml.sqlite"))
    monkeypatch.setattr(TestingConfig, "ML_ARTIFACT_DIR", str(tmp_path / "models"))
    monkeypatch.setattr(TestingConfig, "ML_EPOCHS", 2)
    monkeypatch.setattr(TestingConfig, "ML_LABEL_FILE", None)

    def client(app):
        api = ApiClient(app.test_client())
        assert api.login("admin@example.test", ADMIN_PASSWORD).status_code == 200
        return api

    app = create_app("testing")
    with app.app_context():
        admin = User(email="admin@example.test", full_name="Admin", role="admin")
        admin.set_password(ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.commit()
    api = client(app)
    assert api.post(ROOT + "/predict/fraud", TRANSACTION).status_code == 409
    trained = api.post(ROOT + "/train", {"seed": 42})
    assert trained.status_code == 201, trained.get_json()
    fraud, demand = trained.get_json()["runs"]
    assert fraud["version"] == demand["version"]
    for run in (fraud, demand):
        file = tmp_path / "models" / run["artifact_path"]
        assert file.exists() and file.with_suffix(".json").exists()
    summary = fraud["dataset_summary"]
    assert summary["train"]["last"] < summary["test"]["first"]
    assert sum(fraud["metrics"]["confusion_matrix"].values()) == summary["test"]["size"]
    assert summary["oversampled_train_rows"] > 0
    import tensorflow as tf
    import numpy as np

    with app.app_context():
        train, _, _ = pipeline.fraud_dataset(42)
    persisted = tf.keras.models.load_model(tmp_path / "models" / fraud["artifact_path"], compile=False)
    np.testing.assert_allclose(
        persisted.get_layer("training_normalization").mean.numpy().reshape(-1),
        np.mean([r[1] for r in train], axis=0),
        rtol=1e-5,
        atol=1e-6,
    )
    pred = api.post(ROOT + "/predict/fraud", TRANSACTION)
    assert pred.status_code == 201
    data = pred.get_json()
    assert 0 <= data["fraud_probability"] <= 1 and data["predicted_label"] in ("normal", "fraudulenta")
    # Señales agrupadas: la hora, el método, el canal y el estado del hash se explican como un bloque
    from app.ml.train_models import SIGNAL_GROUPS
    allowed = set(SIGNAL_GROUPS) | {"log_amount", "log_prior_frequency", "discount_fraction", "cancellation_rate"}
    assert {s["feature"] for s in data["signals"]} <= allowed and len(data["signals"]) == 3
    forecast = api.get(ROOT + "/predict/demand?horizon=2&product_id=-1").get_json()
    assert len(forecast["products"][0]["forecast"]) == 2
    assert set(forecast["metrics"]) == {"keras", "linear_phase4"}

    second = create_app("testing")
    api2 = client(second)
    state = api2.get(ROOT + "/status").get_json()["models"]["fraud_classifier"]
    assert state["on_disk"] and not state["loaded"]
    other = api2.post(ROOT + "/predict/fraud", TRANSACTION).get_json()
    assert other["fraud_probability"] == pytest.approx(data["fraud_probability"], abs=1e-7)
    assert api2.get(ROOT + "/predict/demand?horizon=2&product_id=-1").get_json() == forecast
    with second.app_context():
        assert ModelRun.query.count() == 2 and FraudPrediction.query.count() == 2
        assert FraudPrediction.query.first().feature_snapshot["amount"] == 50000
    assert api2.post(ROOT + "/predict/fraud", {"order_id": 999}).status_code == 404

    from app.cli import seed_demo_data
    from tests.test_api import checkout_payload

    with second.app_context():
        seed_demo_data()
        pid = Product.query.first().id
    order = api2.post(
        "/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}], channel="presencial")
    ).get_json()["order"]
    invoice = api2.post(f"/api/orders/{order['id']}/invoice", {"discount_amount": "500.00"}).get_json()[
        "invoice"
    ]
    assert api2.post("/api/admin/integrity/verify").get_json()["status"] == "valid"
    payment = api2.post(
        f"/api/invoices/{invoice['id']}/payments", {"amount": "1.00", "payment_method": "efectivo"}
    ).get_json()["payment"]
    for reference, entity in (("order_id", order), ("invoice_id", invoice), ("payment_id", payment)):
        prediction = api2.post(ROOT + "/predict/fraud", {reference: entity["id"]})
        assert prediction.status_code == 201
        with second.app_context():
            saved = db.session.get(FraudPrediction, prediction.get_json()["id"])
            assert getattr(saved, reference) == entity["id"]
            if reference == "payment_id":
                assert saved.feature_snapshot["hash_valid"] == 1
                assert saved.feature_snapshot["payment_method"] == "efectivo"

    model_file = tmp_path / "models" / fraud["artifact_path"]
    model_file.with_suffix(".json").write_text("{}", encoding="utf-8")
    restarted = client(create_app("testing"))
    assert restarted.post(ROOT + "/predict/fraud", TRANSACTION).status_code == 503


def test_ml_admin_only(api, app, admin_api):
    employee, _ = employee_login(app, admin_api)
    endpoints = [
        ("get", "/status"),
        ("post", "/train"),
        ("get", "/predict/demand"),
        ("post", "/predict/fraud"),
    ]
    for method, path in endpoints:
        assert getattr(api, method)(ROOT + path).status_code == 401
        assert getattr(employee, method)(ROOT + path).status_code == 403
    api.login("cliente@ferrepro.test", CUSTOMER_PASSWORD)
    for method, path in endpoints:
        assert getattr(api, method)(ROOT + path).status_code == 403


def test_real_adjudicated_labels_and_point_in_time_features(app, tmp_path):
    from app.models import OrderStatus, OrderStatusHistory
    from app.models.billing import Invoice, InvoiceItem, Payment
    from tests.test_phase4 import sample_order

    customer = User.query.filter_by(role="customer").one()
    product = Product.query.first()
    lines = ["payment_id,label,adjudicated_at"]
    for i in range(20):
        order = sample_order(customer.id, product, i, 1, 1000)
        when = pipeline.as_utc(order.created_at) + timedelta(minutes=1)
        invoice = Invoice(
            order_id=order.id,
            subtotal=1000,
            discount_amount=100,
            tax_amount=0,
            total_amount=900,
            shipping_cost=0,
            created_at=when,
        )
        invoice.items.append(
            InvoiceItem(
                product_id=product.id,
                name=product.name,
                sku=product.sku,
                quantity=i + 1,
                unit_price=10,
                subtotal=10 * (i + 1),
            )
        )
        db.session.add(invoice)
        db.session.flush()
        payment = Payment(
            order_id=order.id,
            invoice_id=invoice.id,
            amount=900,
            payment_method="tarjeta",
            status="aprobado",
            created_at=when + timedelta(minutes=1),
        )
        db.session.add(payment)
        db.session.flush()
        if i == 0:
            db.session.add(
                OrderStatusHistory(
                    order_id=order.id, new_status=OrderStatus.CANCELLED, created_at=when + timedelta(days=40)
                )
            )
        lines.append(
            f"{payment.id},{'fraudulenta' if i % 2 else 'normal'},{(when + timedelta(hours=1)).isoformat()}"
        )
    db.session.commit()
    labels = tmp_path / "labels.csv"
    labels.write_text("\n".join(lines), encoding="utf-8")
    app.config["ML_LABEL_FILE"] = str(labels)
    train, test, summary = pipeline.fraud_dataset(42)
    assert not summary["simulated_labels"] and len(train) == 16 and len(test) == 4
    assert {row[3] for row in train + test} == {"real"}
    snap = pipeline.operation("payment_id", payment.id)
    assert snap["prior_frequency"] == 19 and snap["cancellation_rate"] == 0
    assert snap["discount_pct"] == 10 and snap["hash_valid"] is None
    series, cutoff, info = pipeline.demand_dataset(42)
    assert info["source"] == "real" and cutoff == date(2026, 1, 17)
    assert series[str(product.id)]["values"] == list(range(1, 21))
    lines[1] = lines[1].rsplit(",", 1)[0] + "," + lines[-1].rsplit(",", 1)[1]
    labels.write_text("\n".join(lines), encoding="utf-8")
    _, _, summary = pipeline.fraud_dataset(42)
    assert summary["late_labels_excluded"] == 1
