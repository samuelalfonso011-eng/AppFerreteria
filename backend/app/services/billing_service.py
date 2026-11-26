from decimal import Decimal, ROUND_HALF_UP

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models.billing import Invoice, InvoiceItem, Payment
from app.models.order import Order, OrderStatus, OrderStatusHistory
from app.services.errors import BusinessError
from app.utils.timeutils import utcnow


def staff_order(order_id, actor, *, lock=False):
    order = db.session.get(Order, order_id, with_for_update=lock, populate_existing=lock)
    if order is None or (not actor.is_admin and order.employee_id != actor.id):
        raise BusinessError("Pedido no encontrado.", code="not_found", status=404)
    return order


def issue_invoice(order, actor, discount):
    existing = Invoice.query.filter_by(order_id=order.id).first()
    if existing is not None:
        return existing, False
    if order.status == OrderStatus.CANCELLED:
        raise BusinessError("El pedido fue cancelado.", code="order_cancelled")
    if discount > order.subtotal:
        raise BusinessError("El descuento supera el subtotal.", code="invalid_discount", status=400)

    rate = current_app.config["INVOICE_TAX_RATE"]
    tax = ((order.subtotal - discount) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    invoice = Invoice(
        order_id=order.id, employee_id=actor.id, subtotal=order.subtotal,
        shipping_cost=order.shipping_cost, tax_amount=tax, discount_amount=discount,
        total_amount=order.subtotal - discount + tax + order.shipping_cost,
        items=[InvoiceItem(product_id=line.product_id, name=line.product_name, sku=line.product_sku,
                           quantity=line.quantity, unit_price=line.unit_price, subtotal=line.subtotal)
               for line in order.items],
    )
    if order.status == OrderStatus.PENDING:
        order.status = OrderStatus.CONFIRMED
        order.history.append(OrderStatusHistory(
            previous_status=OrderStatus.PENDING, new_status=OrderStatus.CONFIRMED,
            changed_by_user_id=actor.id, comment="Pedido confirmado al emitir factura.",
        ))
    db.session.add(invoice)
    db.session.commit()
    return invoice, True


def register_payment(invoice_id, actor, method, amount, receipt_type, receipt_data):
    invoice = db.session.get(Invoice, invoice_id)
    if invoice is None:
        raise BusinessError("Factura no encontrada.", code="not_found", status=404)
    # El mismo bloqueo del pedido serializa las reservas del saldo.
    staff_order(invoice.order_id, actor, lock=True)
    if invoice.status != "emitida":
        raise BusinessError("La factura fue anulada.", code="invoice_void")
    reserved = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.invoice_id == invoice.id, Payment.status.in_(("pendiente", "aprobado")),
    ).scalar()
    if reserved + amount > invoice.total_amount:
        raise BusinessError("El monto supera el saldo disponible.", code="payment_exceeds_balance")
    approved = method in ("efectivo", "tarjeta")
    payment = Payment(
        invoice_id=invoice.id, order_id=invoice.order_id, amount=amount, payment_method=method,
        receipt_type=receipt_type, receipt_data=receipt_data,
        status="aprobado" if approved else "pendiente", paid_at=utcnow() if approved else None,
    )
    db.session.add(payment)
    db.session.commit()
    return payment
