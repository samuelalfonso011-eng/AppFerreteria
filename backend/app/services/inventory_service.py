"""Movimientos de stock atomicos.

Cada descuento es un UPDATE condicional (stock = stock - n WHERE stock >= n), que la base de
datos ejecuta de forma atomica. Dos compras simultaneas nunca pueden dejar el stock negativo,
en PostgreSQL ni en SQLite, sin depender de bloqueos explicitos.
"""
from sqlalchemy import select, update

from app.extensions import db
from app.models import InventoryMovement, MovementType, Product
from app.services.errors import BusinessError, InsufficientStockError


def _current_stock(product_id):
    return db.session.execute(select(Product.stock).where(Product.id == product_id)).scalar_one()


def _record(product, movement_type, quantity, new_stock, previous_stock, user_id, reason, reference):
    db.session.add(InventoryMovement(
        product_id=product.id, user_id=user_id, movement_type=movement_type, quantity=quantity,
        previous_stock=previous_stock, new_stock=new_stock, reason=reason, reference=reference,
    ))


def decrease(product, quantity, movement_type, reason, user_id=None, reference=None):
    result = db.session.execute(
        update(Product)
        .where(Product.id == product.id, Product.stock >= quantity)
        .values(stock=Product.stock - quantity)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise InsufficientStockError(product, quantity, _current_stock(product.id))
    new_stock = _current_stock(product.id)
    db.session.expire(product, ["stock"])
    _record(product, movement_type, quantity, new_stock, new_stock + quantity, user_id, reason, reference)
    return new_stock


def increase(product, quantity, movement_type, reason, user_id=None, reference=None):
    db.session.execute(
        update(Product)
        .where(Product.id == product.id)
        .values(stock=Product.stock + quantity)
        .execution_options(synchronize_session=False)
    )
    new_stock = _current_stock(product.id)
    db.session.expire(product, ["stock"])
    _record(product, movement_type, quantity, new_stock, new_stock - quantity, user_id, reason, reference)
    return new_stock


def restore_for_order(order, user_id, reason):
    for item in order.items:
        product = db.session.get(Product, item.product_id)
        if product is not None:
            increase(product, item.quantity, MovementType.ORDER_CANCEL_RESTORE, reason,
                     user_id=user_id, reference=order.order_number)


def manual_adjustment(product_id, movement_type, quantity, reason, user_id):
    if movement_type not in MovementType.MANUAL:
        raise BusinessError("Tipo de movimiento no permitido.", code="validation", status=400)
    product = db.session.get(Product, product_id)
    if product is None:
        raise BusinessError("Producto no encontrado.", code="not_found", status=404)
    try:
        if movement_type in MovementType.INCREASES:
            increase(product, quantity, movement_type, reason, user_id=user_id)
        else:
            decrease(product, quantity, movement_type, reason, user_id=user_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return db.session.get(Product, product_id)
