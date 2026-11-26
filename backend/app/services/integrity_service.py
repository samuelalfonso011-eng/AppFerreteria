"""Cadena global de eventos financieros. El llamador confirma el documento y su evento juntos."""
import hashlib
import json

from sqlalchemy import func, select, text

from app.extensions import db
from app.models.billing import Invoice, InvoiceItem, Payment
from app.models.integrity import LedgerEntry, Verification

from app.utils.timeutils import as_utc

GENESIS = "GENESIS"
FIELDS = {
    "invoice": ("invoice_number", "order_id", "employee_id", "subtotal", "shipping_cost",
                "tax_amount", "discount_amount", "total_amount", "status", "created_at"),
    "payment": ("invoice_id", "order_id", "amount", "payment_method", "status", "receipt_path", "receipt_type", "created_at", "paid_at"),
}
MONEY = {"subtotal", "shipping_cost", "tax_amount", "discount_amount", "total_amount", "amount"}


def lock_chain():
    if db.session.get_bind().dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(617203581)"))


def compact(values):
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def item_bytes(item):
    return (compact({"id": item.id, "name": item.name, "product_id": item.product_id,
                     "quantity": item.quantity, "sku": item.sku, "subtotal": format(item.subtotal, ".2f"),
                     "unit_price": format(item.unit_price, ".2f")}) + "\n").encode("utf-8")


def canonical(kind, document, attachment_digest):

    payload = {key: getattr(document, key) for key in FIELDS[kind]}
    for key in MONEY.intersection(payload):
        payload[key] = format(payload[key], ".2f")
    for key in ("created_at", "paid_at"):
        if payload.get(key) is not None:
            payload[key] = as_utc(payload[key]).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload["items_sha256" if kind == "invoice" else "receipt_sha256"] = attachment_digest
    return compact(payload)


def snapshot(kind, document):
    if kind == "invoice":
        checksum = hashlib.sha256()
        for item in sorted(document.items, key=lambda item: item.id):
            checksum.update(item_bytes(item))
        return canonical(kind, document, checksum.hexdigest())
    receipt = document.receipt_data
    return canonical(kind, document, hashlib.sha256(receipt).hexdigest() if receipt is not None else None)



def digest(seq, kind, entity_id, event, payload, previous):
    message = f"{seq}|{kind}|{entity_id}|{event}|{payload}|{previous}"
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def append_event(kind, document, event):
    lock_chain()
    db.session.flush()
    tail = LedgerEntry.query.order_by(LedgerEntry.seq_no.desc()).first()
    seq = tail.seq_no + 1 if tail else 1
    previous = tail.current_hash if tail else GENESIS
    payload = snapshot(kind, document)
    db.session.add(LedgerEntry(seq_no=seq, entity_type=kind, entity_id=document.id, event_type=event,
                               canonical_payload=payload, prev_hash=previous,
                               current_hash=digest(seq, kind, document.id, event, payload, previous)))


def verify_chain(checked_by="system"):
    lock_chain()
    entries = LedgerEntry.query.order_by(LedgerEntry.seq_no).populate_existing().all()
    latest = {(row.entity_type, row.entity_id): row.seq_no for row in entries}
    report = Verification(checked_by=checked_by, status="valid", total_records_checked=0, details={})

    def fail(seq, kind, entity_id, reason, expected, actual):
        report.status = "compromised"
        report.first_broken_seq_no = seq
        report.first_broken_entity_type = kind
        report.first_broken_entity_id = entity_id
        report.failure_reason = reason
        report.details = {"expected": expected, "actual": actual}

    documents = {}
    item_hashes = {}
    for item in db.session.scalars(select(InvoiceItem).order_by(InvoiceItem.id).execution_options(yield_per=500)):
        if item.invoice_id not in item_hashes:
            item_hashes[item.invoice_id] = hashlib.sha256()
        item_hashes[item.invoice_id].update(item_bytes(item))
    invoices = select(Invoice.id, *(getattr(Invoice, k) for k in FIELDS["invoice"]))
    for row in db.session.execute(invoices):
        checksum = item_hashes.get(row.id) or hashlib.sha256()
        documents["invoice", row.id] = canonical("invoice", row, checksum.hexdigest())
    postgres = db.session.get_bind().dialect.name == "postgresql"
    receipt = func.encode(func.sha256(Payment.receipt_data), "hex") if postgres else Payment.receipt_data
    payments = select(Payment.id, *(getattr(Payment, k) for k in FIELDS["payment"]), receipt.label("receipt"))
    for row in db.session.execute(payments.execution_options(yield_per=1)):
        checksum = row.receipt
        if not postgres and checksum is not None:
            checksum = hashlib.sha256(checksum).hexdigest()
        documents["payment", row.id] = canonical("payment", row, checksum)
    checkpoints = {audit.total_records_checked: audit.details["head_hash"]
                   for audit in Verification.query.filter_by(status="valid").order_by(Verification.id)
                   if "head_hash" in audit.details}
    previous = GENESIS
    for position, row in enumerate(entries, 1):
        key = (row.entity_type, row.entity_id)
        report.total_records_checked = position
        if row.seq_no != position:
            fail(position, None, None, "sequence_gap", position, row.seq_no)
        elif row.prev_hash != previous:
            fail(position, *key, "prev_hash_broken", previous, row.prev_hash)
        else:
            expected = digest(position, *key, row.event_type, row.canonical_payload, previous)
            if expected != row.current_hash:
                fail(position, *key, "hash_mismatch", expected, row.current_hash)
            elif position in checkpoints and checkpoints[position] != row.current_hash:
                fail(position, *key, "checkpoint_mismatch", checkpoints[position], row.current_hash)
            elif latest[key] == position:
                actual = documents.get(key)
                if actual is None:
                    fail(position, *key, "missing_entity", row.canonical_payload, None)
                elif actual != row.canonical_payload:
                    fail(position, *key, "payload_mismatch", row.canonical_payload, actual)
        if report.status == "compromised":
            break
        previous = row.current_hash
    else:
        missing = min(documents.keys() - latest.keys(), default=None)
        if missing:
            fail(None, *missing, "missing_event", "ledger_entry", None)
        else:
            checkpoint = (Verification.query.filter_by(status="valid")
                          .order_by(Verification.total_records_checked.desc(), Verification.id.desc()).first())
            if checkpoint and checkpoint.total_records_checked > len(entries):
                fail(len(entries) + 1, None, None, "sequence_gap", checkpoint.total_records_checked, len(entries))
    if report.status == "valid":
        report.details = {"head_hash": previous}
    db.session.add(report)
    db.session.commit()
    return report
