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
    assert after == pytest.approx(before - 1000)

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
