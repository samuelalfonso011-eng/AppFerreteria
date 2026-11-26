import logging
import secrets
from datetime import timedelta
from decimal import Decimal

from flask import current_app
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.legal.content import POLICY_VERSION
from app.models import (MovementType, Order, OrderItem, OrderStatus, OrderStatusHistory, Product,
                        StoreSetting, record_consent)
from app.services import inventory_service
from app.services.errors import BusinessError
from app.utils.cache import cache
from app.utils.timeutils import BOGOTA, utcnow

logger = logging.getLogger(__name__)


def generate_order_number():
    return "FP-" + utcnow().astimezone(BOGOTA).strftime("%y%m%d") + "-" + secrets.token_hex(3).upper()


def create_order(customer, items, idempotency_key, expected_total=None, ip_address=None, *,
                 channel="web", customer_id=None, employee_id=None):
    """Crea el pedido de forma atomica: precios del servidor, stock reservado, consentimiento.

    items: dict {product_id: quantity} ya validado.
    Devuelve (order, created). Si la clave de idempotencia ya existe, devuelve ese pedido.
    """
    maybe_expire_stale_orders()

    def same_checkout(order):
        return (order.customer_email == customer["customer_email"] and order.channel == channel
                and order.customer_id == customer_id and order.employee_id == employee_id)

    existing = Order.query.filter_by(idempotency_key=idempotency_key).first()
    if existing:
        if not same_checkout(existing):
            raise BusinessError("Este pedido ya fue registrado con otros datos. Recarga la página.",
                                code="idempotency")
        return existing, False

    ids = sorted(items)
    products = {p.id: p for p in Product.query.filter(Product.id.in_(ids)).all()}
    unavailable = [pid for pid in ids
                   if pid not in products or not products[pid].is_active or not products[pid].category.is_active]
    if unavailable:
        raise BusinessError("Algunos productos de tu carrito ya no están disponibles. Revisa el carrito.",
                            code="unavailable", product_ids=unavailable)

    subtotal = sum((Decimal(products[pid].price) * items[pid] for pid in ids), Decimal("0"))
    shipping = Decimal("0.00") if channel == "presencial" else StoreSetting.get().calculate_shipping(subtotal)
    total = subtotal + shipping

    if expected_total is not None and Decimal(expected_total) != total:
        raise BusinessError("Los precios cambiaron mientras comprabas. Revisa el nuevo total antes de confirmar.",
                            code="price_changed", total=int(total) if total == total.to_integral_value() else float(total))

    number = generate_order_number()
    now = utcnow()
    try:
        order = Order(
            order_number=number, status=OrderStatus.PENDING, subtotal=subtotal, shipping_cost=shipping,
            total=total, idempotency_key=idempotency_key, policy_version=POLICY_VERSION,
            terms_accepted_at=now, privacy_accepted_at=now, created_at=now, updated_at=now,
            channel=channel, customer_id=customer_id, employee_id=employee_id, **customer,
        )
        db.session.add(order)
        # Reclama la clave antes de tocar el stock, incluso si dos envíos llegan juntos.
        db.session.flush()
        for pid in ids:
            inventory_service.decrease(products[pid], items[pid], MovementType.SALE_EXIT,
                                       f"Venta del pedido {number}", user_id=employee_id, reference=number)
            product = products[pid]
            order.items.append(OrderItem(
                product_id=pid, product_name=product.name, product_sku=product.sku,
                unit_price=product.price, quantity=items[pid],
                subtotal=Decimal(product.price) * items[pid],
            ))
        order.history.append(OrderStatusHistory(
            previous_status=None, new_status=OrderStatus.PENDING,
            comment=f"Pedido registrado por canal {channel}.", changed_by_user_id=employee_id, created_at=now,
        ))
        db.session.flush()
        record_consent("checkout", "terms", accepted_at=now, order_id=order.id, ip_address=ip_address)
        record_consent("checkout", "habeas_data", accepted_at=now, order_id=order.id, ip_address=ip_address)
        db.session.commit()
        return order, True
    except IntegrityError:
        db.session.rollback()
        # Doble envio simultaneo con la misma clave: devolver el pedido que si se guardo
        existing = Order.query.filter_by(idempotency_key=idempotency_key).first()
        if existing:
            if same_checkout(existing):
                return existing, False
            raise BusinessError("Este pedido ya fue registrado con otros datos.", code="idempotency")
        raise
    except Exception:
        db.session.rollback()
        raise


def change_status(order_id, new_status, user_id=None, comment=None):
    """Aplica una transicion valida. El UPDATE condicional evita dobles cancelaciones concurrentes."""
    from app.models.billing import Invoice

    order = db.session.get(Order, order_id, with_for_update=True, populate_existing=True)
    if order is None:
        raise BusinessError("Pedido no encontrado.", code="not_found", status=404)
    if new_status not in OrderStatus.ALL:
        raise BusinessError("Estado no válido.", code="validation", status=400)
    previous = order.status
    if new_status not in OrderStatus.TRANSITIONS.get(previous, ()):
        raise BusinessError(
            f"No se puede pasar de {OrderStatus.LABELS[previous]} a {OrderStatus.LABELS[new_status]}.",
            code="transition")
    if new_status == OrderStatus.CANCELLED and Invoice.query.filter_by(order_id=order.id, status="emitida").first():
        raise BusinessError("El pedido tiene una factura emitida.", code="order_invoiced")
    now = utcnow()
    try:
        result = db.session.execute(
            update(Order).where(Order.id == order_id, Order.status == previous)
            .values(status=new_status, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise BusinessError("El pedido cambió mientras lo editabas. Recarga para ver su estado actual.",
                                code="stale")
        db.session.expire(order, ["status", "updated_at"])
        if new_status == OrderStatus.CANCELLED:
            inventory_service.restore_for_order(order, user_id, comment or "Cancelación del pedido")
        db.session.add(OrderStatusHistory(order_id=order.id, previous_status=previous, new_status=new_status,
                                          changed_by_user_id=user_id, comment=comment, created_at=now))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return db.session.get(Order, order_id)


def expire_stale_orders(minutes):
    cutoff = utcnow() - timedelta(minutes=minutes)
    stale = [row[0] for row in db.session.query(Order.id)
             .filter(Order.status == OrderStatus.PENDING, Order.created_at < cutoff).all()]
    expired = 0
    for order_id in stale:
        try:
            change_status(order_id, OrderStatus.CANCELLED, None,
                          f"Cancelado automáticamente: sin confirmar tras {minutes} minutos.")
            expired += 1
        except BusinessError:
            db.session.rollback()
            continue
    return expired


def maybe_expire_stale_orders(every_seconds=60):
    """Libera el stock de pedidos abandonados como maximo una vez por minuto, sin cron."""
    minutes = current_app.config.get("ORDER_PENDING_EXPIRY_MINUTES", 0)
    if not minutes or cache.get("maintenance:order_expiry"):
        return
    cache.set("maintenance:order_expiry", True, ttl=every_seconds)
    try:
        expire_stale_orders(minutes)
    except Exception:
        db.session.rollback()
        logger.exception("Fallo al vencer pedidos pendientes")
