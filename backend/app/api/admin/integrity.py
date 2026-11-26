from flask import jsonify, request

from app.api.admin import admin_bp
from app.models.integrity import LedgerEntry, Verification
from app.services import billing_service, integrity_service
from app.utils.security import current_user


@admin_bp.get("/integrity/status")
def integrity_status():
    integrity_service.lock_chain()
    count = LedgerEntry.query.count()
    last = Verification.query.order_by(Verification.id.desc()).first()
    recent = LedgerEntry.query.order_by(LedgerEntry.seq_no.desc()).limit(5).all()
    status = "unverified"
    if last and (last.status == "compromised" or last.total_records_checked == count):
        status = last.status
    return jsonify(status=status, total_records=count, last_verification=last.to_dict() if last else None,
                   recent_events=[entry.summary() for entry in recent])


@admin_bp.post("/integrity/verify")
def verify_integrity():
    return jsonify(integrity_service.verify_chain(f"admin:{current_user().id}").to_dict())


@admin_bp.get("/integrity/chain")
def integrity_chain():
    page = request.args.get("page", 1, type=int)
    size = request.args.get("per_page", 25, type=int)
    rows = LedgerEntry.query.order_by(LedgerEntry.seq_no.desc()).paginate(
        page=max(1, page), per_page=max(1, min(100, size)), error_out=False)
    return jsonify(entries=[entry.summary() for entry in rows.items], page=rows.page,
                   per_page=rows.per_page, pages=rows.pages, total=rows.total)


@admin_bp.post("/payments/<int:payment_id>/status")
def review_payment(payment_id):
    """Aprueba o rechaza un pago pendiente. Solo admin (guardia del blueprint)."""
    from app.utils.validation import Validator

    v = Validator(request.get_json(silent=True))
    decision = v.choice("status", billing_service.PAYMENT_DECISIONS)
    v.raise_if_errors()
    payment, changed = billing_service.review_payment(payment_id, current_user(), decision)
    return jsonify(payment=payment.to_dict(), changed=changed)


@admin_bp.post("/invoices/<int:invoice_id>/void")
def void_invoice(invoice_id):
    return jsonify(invoice=billing_service.void_invoice(invoice_id, current_user()).to_dict())
