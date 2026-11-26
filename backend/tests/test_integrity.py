import hashlib
import json

import pytest
from sqlalchemy import text

from app.extensions import db
from app.models import Product
from app.models.integrity import LedgerEntry, Verification
from tests.test_api import checkout_payload
from tests.test_phase1 import employee_login
from tests.conftest import CUSTOMER_PASSWORD

ROOT = "/api/admin/integrity"


@pytest.fixture
def invoice(admin_api):
    payload = checkout_payload([{"product_id": Product.query.first().id, "quantity": 1}])
    order = admin_api.post("/api/orders", payload).get_json()["order"]
    route = f"/api/orders/{order['id']}/invoice"
    first = admin_api.post(route)
    assert first.status_code == 201
    assert admin_api.post(route).status_code == 200
    return first.get_json()["invoice"]


def payment(admin_api, invoice):
    response = admin_api.post(f"/api/invoices/{invoice['id']}/payments",
                              {"payment_method": "efectivo", "amount": "10.50"})
    assert response.status_code == 201
    return response.get_json()["payment"]


def verify(admin_api):
    response = admin_api.post(ROOT + "/verify")
    assert response.status_code == 200
    return response.get_json()


def test_chain_and_history(admin_api, invoice):
    paid = payment(admin_api, invoice)
    rows = LedgerEntry.query.order_by(LedgerEntry.seq_no).all()
    assert [(r.seq_no, r.entity_type, r.entity_id) for r in rows] == [
        (1, "invoice", invoice["id"]), (2, "payment", paid["id"])]
    previous = "GENESIS"
    for row in rows:
        assert row.prev_hash == previous
        message = "|".join(map(str, (row.seq_no, row.entity_type, row.entity_id, row.event_type,
                                     row.canonical_payload, previous)))
        previous = hashlib.sha256(message.encode()).hexdigest()
        assert row.current_hash == previous
    report = verify(admin_api)
    assert report["status"] == "valid" and report["total_records_checked"] == 2
    assert report["checked_by"].startswith("admin:")
    status = admin_api.get(ROOT + "/status").get_json()
    assert status["last_verification"] == report and status["total_records"] == 2
    chain = admin_api.get(ROOT + "/chain?per_page=1&page=2").get_json()
    assert chain["pages"] == 2 and chain["entries"][0]["current_hash"] == rows[0].current_hash


def test_altered_invoice_is_first_divergence(admin_api, invoice):
    payment(admin_api, invoice)
    # Conserva la ecuación contable exigida por el CHECK de Fase 1.
    db.session.execute(text("UPDATE invoices SET total_amount=total_amount+1, tax_amount=tax_amount+1 WHERE id=:id"),
                       {"id": invoice["id"]})
    db.session.commit()
    report = verify(admin_api)
    assert (report["status"], report["failure_reason"], report["first_broken_seq_no"],
            report["first_broken_entity_type"], report["first_broken_entity_id"]) == (
                "compromised", "payload_mismatch", 1, "invoice", invoice["id"])
    assert json.loads(report["details"]["expected"])["total_amount"] == invoice["total_amount"]
    assert json.loads(report["details"]["actual"])["total_amount"] != invoice["total_amount"]
    assert Verification.query.one().status == "compromised"


@pytest.mark.parametrize(("column", "reason"), [("current_hash", "hash_mismatch"), ("prev_hash", "prev_hash_broken")])
def test_corrupt_link(admin_api, invoice, column, reason):
    paid = payment(admin_api, invoice)
    row = LedgerEntry.query.filter_by(seq_no=2).one()
    setattr(row, column, "0" * 64)
    db.session.commit()
    report = verify(admin_api)
    assert (report["first_broken_seq_no"], report["first_broken_entity_id"], report["failure_reason"]) == (
        2, paid["id"], reason)


def test_void_appends_and_preserves_issued_snapshot(admin_api, invoice):
    first_hash = LedgerEntry.query.one().current_hash
    route = f"/api/admin/invoices/{invoice['id']}/void"
    assert admin_api.post(route).get_json()["invoice"]["status"] == "anulada"
    assert admin_api.post(route).status_code == 200
    assert LedgerEntry.query.count() == 2
    assert LedgerEntry.query.filter_by(event_type="voided").one().prev_hash == first_hash
    assert verify(admin_api)["status"] == "valid"


def test_integrity_admin_only(app, api, admin_api):
    employee, _ = employee_login(app, admin_api)
    for method, path in [("get", "/status"), ("get", "/chain"), ("post", "/verify")]:
        assert getattr(api, method)(ROOT + path).status_code == 401
        assert getattr(employee, method)(ROOT + path).status_code == 403
    assert api.login("cliente@ferrepro.test", CUSTOMER_PASSWORD).status_code == 200
    assert api.post(ROOT + "/verify").status_code == 403
    assert Verification.query.count() == 0


def test_missing_payment_and_atomic_rollback(admin_api, invoice, monkeypatch):
    from app.services import integrity_service

    with monkeypatch.context() as scoped:
        def fail(*args):
            raise RuntimeError("Simulación de fallo al encadenar")
        scoped.setattr(integrity_service, "append_event", fail)
        response = admin_api.post(f"/api/invoices/{invoice['id']}/payments",
                                  {"payment_method": "efectivo", "amount": "1.00"})
        assert response.status_code == 500
    assert db.session.execute(text("select count(*) from payments")).scalar() == 0
    paid = payment(admin_api, invoice)
    db.session.execute(text("delete from payments where id=:id"), {"id": paid["id"]})
    db.session.commit()
    report = verify(admin_api)
    assert report["failure_reason"] == "missing_entity" and report["first_broken_seq_no"] == 2
