"""Correcciones de la auditoría cruzada: simulador sin fuga, pagos pendientes resolubles y entrenamiento en segundo plano."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.extensions import db
from app.ml import data_pipeline as pipeline
from app.ml import train_models
from app.models import Product
from app.models.billing import Payment
from app.models.integrity import LedgerEntry
from app.services.errors import BusinessError
from tests.conftest import CUSTOMER_PASSWORD
from tests.test_api import checkout_payload
from tests.test_phase1 import employee_login

HASH_INVALID = 4  # posición de hash_invalid en fraud_vector()


# ------------------------------------------------------------ 1. simulador sin fuga de la etiqueta

def test_simulated_hash_divergence_overlaps_between_classes():
    rows = pipeline.simulated_transactions(42, datetime(2025, 1, 1, tzinfo=timezone.utc))
    invalid = [row for row in rows if row[1][HASH_INVALID] == 1]
    labels = {row[2] for row in invalid}
    # La divergencia aparece en ambas clases: ya no identifica el fraude por sí sola
    assert labels == {0, 1}
    fraud_rate = sum(r[1][HASH_INVALID] for r in rows if r[2] == 1) / sum(1 for r in rows if r[2] == 1)
    normal_rate = sum(r[1][HASH_INVALID] for r in rows if r[2] == 0) / sum(1 for r in rows if r[2] == 0)
    assert fraud_rate > normal_rate  # sigue siendo una señal, no una etiqueta
    assert pipeline.simulated_transactions(42, datetime(2025, 1, 1, tzinfo=timezone.utc)) == rows  # determinista


@pytest.mark.parametrize("index,name", [(1, "log_prior_frequency"), (2, "discount_fraction"), (3, "cancellation_rate")])
def test_simulated_features_share_support_between_classes(index, name):
    """Ningún rango de valores es exclusivo del fraude: con rangos anidados el techo normal delataba la etiqueta."""
    rows = pipeline.simulated_transactions(42, datetime(2025, 1, 1, tzinfo=timezone.utc))
    normal = [r[1][index] for r in rows if r[2] == 0]
    fraud = sorted(r[1][index] for r in rows if r[2] == 1)
    top_fraud = fraud[int(0.8 * len(fraud))]  # percentil 80 del fraude
    assert max(normal) >= top_fraud, name  # los valores altos aparecen también en operaciones normales
    assert sum(fraud) / len(fraud) > sum(normal) / len(normal), name  # pero siguen siendo más típicos del fraude


# ------------------------------------------------------------ 2. pagos pendientes: aprobar o rechazar

@pytest.fixture
def invoiced(app, admin_api):
    pid = Product.query.first().id
    order = admin_api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 1}],
                                                           channel="presencial")).get_json()["order"]
    invoice = admin_api.post(f"/api/orders/{order['id']}/invoice", {}).get_json()["invoice"]
    return order, invoice


def pay(admin_api, invoice, method="transferencia", amount="1000.00"):
    response = admin_api.post(f"/api/invoices/{invoice['id']}/payments", {"payment_method": method, "amount": amount})
    assert response.status_code == 201, response.get_json()
    return response.get_json()["payment"]


def review(client, payment_id, status):
    return client.post(f"/api/admin/payments/{payment_id}/status", {"status": status})


def test_approve_pending_payment_updates_balance_and_chain(admin_api, invoiced):
    order, invoice = invoiced
    payment = pay(admin_api, invoice)
    assert payment["status"] == "pendiente" and payment["paid_at"] is None
    before = admin_api.get(f"/api/orders/{order['id']}/invoice").get_json()["balance"]

    response = review(admin_api, payment["id"], "aprobado")
    assert response.status_code == 200
    body = response.get_json()
    assert body["changed"] is True and body["payment"]["status"] == "aprobado" and body["payment"]["paid_at"]
    after = admin_api.get(f"/api/orders/{order['id']}/invoice").get_json()["balance"]
    assert isinstance(after, str) and Decimal(after) == Decimal(before) - Decimal("1000.00")  # texto exacto, sin float

    events = LedgerEntry.query.filter_by(entity_type="payment", entity_id=payment["id"]).order_by(LedgerEntry.seq_no).all()
    assert [e.event_type for e in events] == ["payment_recorded", "adjustment"]
    assert admin_api.post("/api/admin/integrity/verify").get_json()["status"] == "valid"

    retry = review(admin_api, payment["id"], "aprobado")  # idempotente: sin evento nuevo
    assert retry.status_code == 200 and retry.get_json()["changed"] is False
    assert LedgerEntry.query.filter_by(entity_type="payment", entity_id=payment["id"]).count() == 2
    conflict = review(admin_api, payment["id"], "rechazado")
    assert conflict.status_code == 409 and conflict.get_json()["error"] == "payment_not_pending"


def test_reject_releases_reserved_amount(admin_api, invoiced):
    _, invoice = invoiced
    total = invoice["total_amount"]
    first = pay(admin_api, invoice, "nequi", total)  # reserva todo el saldo
    blocked = admin_api.post(f"/api/invoices/{invoice['id']}/payments", {"payment_method": "efectivo", "amount": "1.00"})
    assert blocked.status_code == 409
    assert review(admin_api, first["id"], "rechazado").get_json()["payment"]["status"] == "rechazado"
    assert db.session.get(Payment, first["id"]).paid_at is None
    assert pay(admin_api, invoice, "efectivo", total)["status"] == "aprobado"  # el saldo volvió a estar disponible
    assert admin_api.post("/api/admin/integrity/verify").get_json()["status"] == "valid"


def test_review_validation_permissions_and_tampering(app, api, admin_api, invoiced):
    _, invoice = invoiced
    payment = pay(admin_api, invoice, "pse")
    assert review(admin_api, payment["id"], "aprobar").status_code == 400
    assert review(admin_api, 999999, "aprobado").status_code == 404
    assert review(api, payment["id"], "aprobado").status_code == 401
    employee, _ = employee_login(app, admin_api)
    assert review(employee, payment["id"], "aprobado").status_code == 403
    api.login("cliente@ferrepro.test", CUSTOMER_PASSWORD)
    assert review(api, payment["id"], "aprobado").status_code == 403
    # Un cambio directo en la base no se puede "legitimar" aprobando el pago
    db.session.execute(text("UPDATE payments SET payment_method='nequi' WHERE id=:id"), {"id": payment["id"]})
    db.session.commit()
    tampered = review(admin_api, payment["id"], "aprobado")
    assert tampered.status_code == 409 and tampered.get_json()["error"] == "integrity_conflict"
    assert db.session.get(Payment, payment["id"]).status == "pendiente"


# ------------------------------------------------------------ 3. entrenamiento en segundo plano

@pytest.fixture
def async_training(app, tmp_path, monkeypatch):
    app.config.update(ML_TRAIN_ASYNC=True, ML_ARTIFACT_DIR=str(tmp_path / "models"))
    threads = []
    import threading

    real_thread = threading.Thread

    class Recorded(real_thread):
        def start(self):
            threads.append(self)
            super().start()

    monkeypatch.setattr(threading, "Thread", Recorded)
    yield threads
    for thread in threads:
        thread.join(timeout=30)


def wait(threads):
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()


def test_train_returns_202_and_status_reports_success(admin_api, async_training, monkeypatch):
    monkeypatch.setattr(train_models, "_train_locked", lambda seed: [{"version": "abc123" * 5 + "ab"}])
    response = admin_api.post("/api/admin/ml/train", {"seed": 7})
    assert response.status_code == 202
    job = response.get_json()["training"]
    assert job["state"] == "running" and job["seed"] == 7 and job["started_at"]
    wait(async_training)
    status = admin_api.get("/api/admin/ml/status").get_json()
    assert status["training"]["state"] == "succeeded" and status["training"]["version"].startswith("abc123")
    assert status["training"]["finished_at"] and "models" in status


def test_background_failure_is_reported_and_lock_released(admin_api, async_training, monkeypatch):
    def broken(seed):
        raise BusinessError("Faltan etiquetas posteriores para evaluar.", code="insufficient_test")

    monkeypatch.setattr(train_models, "_train_locked", broken)
    assert admin_api.post("/api/admin/ml/train", {}).status_code == 202
    wait(async_training)
    job = admin_api.get("/api/admin/ml/status").get_json()["training"]
    assert job["state"] == "failed" and job["error"] == "insufficient_test"
    assert train_models.TRAIN_LOCK.acquire(blocking=False)  # el hilo liberó el candado
    train_models.TRAIN_LOCK.release()


def test_concurrent_and_stale_jobs(app, admin_api, async_training):
    assert train_models.TRAIN_LOCK.acquire(blocking=False)
    try:
        busy = admin_api.post("/api/admin/ml/train", {})
        assert busy.status_code == 409 and busy.get_json()["error"] == "training_busy"
    finally:
        train_models.TRAIN_LOCK.release()
    with app.app_context():
        root = train_models.artifact_root()
        root.mkdir(parents=True, exist_ok=True)
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        (root / train_models.STATE_FILE).write_text(json.dumps({"state": "running", "started_at": old}), encoding="utf-8")
        assert train_models.training_state()["error"] == "training_stalled"
        fresh = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        (root / train_models.STATE_FILE).write_text(json.dumps({"state": "running", "started_at": fresh}), encoding="utf-8")
    # Otro worker tiene un trabajo en curso (archivo compartido): no se inicia otro
    assert admin_api.post("/api/admin/ml/train", {}).status_code == 409


# ============================================================ hallazgos bajos

from decimal import Decimal  # noqa: E402

from app.models import Category, User  # noqa: E402
from app.models.analytics import AnomalyAlert, QualityIssue  # noqa: E402
from app.services.data_quality_service import category_case  # noqa: E402
from tests.test_phase4 import sample_order  # noqa: E402


def test_amount_outliers_use_only_previous_history(admin_api):
    customer = User.query.filter_by(role="customer").one()
    product = Product.query.first()
    # Una compra grande al inicio no tiene historial previo: antes se marcaba con cercas que usaban el futuro
    for i, amount in enumerate([5000, 100, 110, 90, 105, 95]):
        sample_order(customer.id, product, i, 1, amount)
    db.session.commit()
    alerts = admin_api.get("/api/admin/analytics/users").get_json()["alerts"]
    assert not [a for a in alerts if a["alert_type"] == "high_amount_outlier"]
    late = sample_order(customer.id, product, 10, 1, 4000)  # ahora sí supera su historial previo
    db.session.commit()
    alerts = admin_api.get("/api/admin/analytics/users").get_json()["alerts"]
    high = next(a for a in alerts if a["alert_type"] == "high_amount_outlier")
    assert high["source_record_ids"] == {"order_ids": [late.id]} and high["threshold_info"]["n"] == 6
    assert AnomalyAlert.query.count() == 0  # GET no escribe


def test_profiles_expose_rates_for_frequency(admin_api):
    data = admin_api.get("/api/admin/analytics/users").get_json()
    roles = {p["user_role"] for p in data["profiles"]}
    assert "customer" in roles
    for profile in data["profiles"]:
        assert ("orders_per_day" if profile["user_role"] == "customer" else "invoices_per_day") in profile


def test_category_case_respects_mixed_case_and_acronyms():
    assert category_case("ELÉCTRICAS DE MANO") == "Eléctricas de mano"
    assert category_case("pinturas") == "Pinturas"
    assert category_case("Bombillas LED") == "Bombillas LED"
    assert category_case("Tubería PVC") == "Tubería PVC"
    assert category_case("123") == "123"


def test_duplicate_categories_and_resolving_issues(app, api, admin_api):
    first, second = Category.query.order_by(Category.id).limit(2).all()
    first.name, second.name = "Tubería PVC", "tubería pvc"
    db.session.commit()
    report = admin_api.post("/api/admin/data-quality/audit").get_json()
    names = [i for i in report["issues"] if i["module"] == "categories" and i["details"].get("field") == "name"
             and i["entity_id"] in (first.id, second.id)]
    dup = [i for i in names if i["issue_type"] == "duplicate_candidate"]
    assert {i["entity_id"] for i in dup} == {first.id, second.id}
    assert not [i for i in names if i["issue_type"] == "inconsistent_category"]  # reservado a categorías huérfanas
    # "tubería pvc" (todo minúsculas) recibe una propuesta de mayúscula, pero queda en revisión por ser ambiguo
    assert all(i["status"] == "pending_review" for i in names)
    assert db.session.get(Category, first.id).name == "Tubería PVC"  # la sigla se conserva
    pending = dup[0]
    resolved = admin_api.post(f"/api/admin/data-quality/issues/{pending['id']}/resolve")
    assert resolved.status_code == 200 and resolved.get_json()["issue"]["status"] == "resolved"
    assert resolved.get_json()["changed"] is True
    assert admin_api.post(f"/api/admin/data-quality/issues/{pending['id']}/resolve").get_json()["changed"] is False
    latest = admin_api.get("/api/admin/data-quality/latest").get_json()
    assert next(i for i in latest["issues"] if i["id"] == pending["id"])["status"] == "resolved"
    fixed = QualityIssue.query.filter_by(status="auto_fixed").first()
    if fixed:
        conflict = admin_api.post(f"/api/admin/data-quality/issues/{fixed.id}/resolve")
        assert conflict.status_code == 409 and conflict.get_json()["error"] == "issue_not_pending"
    assert admin_api.post("/api/admin/data-quality/issues/999999/resolve").status_code == 404
    employee, _ = employee_login(app, admin_api)
    for client, code in ((api, 401), (employee, 403)):
        assert client.post(f"/api/admin/data-quality/issues/{pending['id']}/resolve").status_code == code
        assert client.post("/api/admin/analytics/users").status_code == code


def test_https_redirect_keeps_method(app):
    app.testing = False
    try:
        response = app.test_client().post("http://tienda.example/api/orders", json={})
        assert response.status_code == 308
        assert response.headers["Location"].startswith("https://tienda.example/api/orders")
    finally:
        app.testing = True


def test_demand_trains_every_evaluated_lead():
    assert list(train_models.DEMAND_LEADS) == list(range(1, 31))


def test_failed_commit_removes_published_artifacts(app, tmp_path, monkeypatch):
    app.config.update(ML_ARTIFACT_DIR=str(tmp_path / "models"), ML_EPOCHS=1)

    class FakeModel:
        def save(self, path):
            path.write_bytes(b"modelo")

    def fake(seed, epochs):
        return FakeModel(), {}, {}, {"features": []}

    monkeypatch.setattr(train_models, "classifier", fake)
    monkeypatch.setattr(train_models, "regressor", fake)

    def broken_commit():
        raise RuntimeError("la base no confirmó")

    monkeypatch.setattr(db.session, "commit", broken_commit)
    with pytest.raises(RuntimeError):
        train_models.train(42)
    root = tmp_path / "models"
    assert [p.name for p in root.iterdir() if not p.name.startswith(".")] == []  # sin versiones huérfanas
