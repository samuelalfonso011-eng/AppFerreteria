from decimal import Decimal
from io import BytesIO

from flask import abort, jsonify, request, send_file

from app.api import api_bp
from app.extensions import db
from app.models.billing import PAYMENT_METHODS, Invoice, Payment
from app.services import billing_service
from app.utils.security import current_user
from app.utils.validation import ValidationError, Validator

MAX_RECEIPT_SIZE = 5 * 1024 * 1024
RECEIPT_FORMATS = {
    "application/pdf": (b"%PDF-", b"%%EOF", "pdf"),
    "image/png": (b"\x89PNG\r\n\x1a\n", b"IEND\xaeB\x60\x82", "png"),
    "image/jpeg": (b"\xff\xd8\xff", b"\xff\xd9", "jpg"),
}


def _staff():
    user = current_user()
    if user is None:
        abort(401)
    if not user.is_staff:
        abort(403)
    return user


@api_bp.get("/orders/<int:order_id>/invoice")
def get_invoice(order_id):
    order = billing_service.staff_order(order_id, _staff())
    invoice = Invoice.query.filter_by(order_id=order.id).one_or_none()
    if invoice is None:
        return jsonify(invoice=None, payments=[], balance="0.00")

    payments = Payment.query.filter_by(invoice_id=invoice.id).order_by(Payment.id).all()
    approved = sum((payment.amount for payment in payments if payment.status == "aprobado"), Decimal("0"))
    # Texto con 2 decimales, como todos los importes de la factura: un número JSON (float) redondea dinero.
    balance = format(max(Decimal("0"), invoice.total_amount - approved).quantize(Decimal("0.01")), ".2f")
    return jsonify(invoice=invoice.to_dict(), payments=[payment.to_dict() for payment in payments], balance=balance)


@api_bp.post("/orders/<int:order_id>/invoice")
def issue_invoice(order_id):
    actor = _staff()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError({"invoice": "Envía un objeto JSON con los datos de facturación."})
    v = Validator(payload)
    discount = v.money("discount_amount", required=False)
    v.raise_if_errors()
    order = billing_service.staff_order(order_id, actor, lock=True)
    invoice, created = billing_service.issue_invoice(order, actor, discount or Decimal("0.00"))
    return jsonify(invoice=invoice.to_dict(), created=created), 201 if created else 200


def _receipt():
    files = request.files.getlist("receipt")
    if not files:
        return None, None
    if len(files) != 1 or not files[0].filename:
        raise ValidationError({"receipt": "Adjunta un solo comprobante."})
    upload = files[0]
    data = upload.stream.read(MAX_RECEIPT_SIZE + 1)
    if len(data) > MAX_RECEIPT_SIZE:
        abort(413)
    file_format = RECEIPT_FORMATS.get(upload.mimetype)
    if file_format is None:
        raise ValidationError({"receipt": "Adjunta un archivo PDF, PNG o JPEG válido."})
    prefix, suffix, _ = file_format
    ending = data.rstrip(b" \t\r\n") if upload.mimetype == "application/pdf" else data
    if not data.startswith(prefix) or not ending.endswith(suffix) or len(data) <= len(prefix) + len(suffix):
        raise ValidationError({"receipt": "Adjunta un archivo PDF, PNG o JPEG válido."})
    return upload.mimetype, data


@api_bp.post("/invoices/<int:invoice_id>/payments")
def register_payment(invoice_id):
    actor = _staff()
    if request.mimetype == "multipart/form-data":
        payload = request.form.to_dict()
    else:
        payload = request.get_json(silent=True)
    v = Validator(payload)
    method = v.choice("payment_method", PAYMENT_METHODS)
    amount = v.money("amount", min_value=Decimal("0.01"), max_value=Decimal("999999999999.99"))
    v.raise_if_errors()
    receipt_type, receipt_data = _receipt()
    payment = billing_service.register_payment(invoice_id, actor, method, amount, receipt_type, receipt_data)
    return jsonify(payment=payment.to_dict()), 201


@api_bp.get("/payments/<int:payment_id>/receipt")
def download_receipt(payment_id):
    actor = _staff()
    payment = db.session.get(Payment, payment_id)
    if payment is None or not payment.receipt_type:
        abort(404)
    billing_service.staff_order(payment.order_id, actor)
    _, _, extension = RECEIPT_FORMATS[payment.receipt_type]
    response = send_file(BytesIO(payment.receipt_data), mimetype=payment.receipt_type, as_attachment=True,
                         download_name=f"comprobante-{payment.id}.{extension}", max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    return response
