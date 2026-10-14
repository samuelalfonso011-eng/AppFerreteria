from app.extensions import db
from app.models.product import Product
from app.models.inventory import InventoryMovement, MovementType
from app.models.order import Order


class InsufficientStockError(Exception):
    """Excepción lanzada cuando la cantidad solicitada supera las existencias disponibles."""
    def __init__(self, product_name: str, available: int, requested: int):
        self.product_name = product_name
        self.available = available
        self.requested = requested
        super().__init__(f"Stock insuficiente para '{product_name}'. Disponibles: {available}, solicitados: {requested}.")


class InventoryService:
    """Servicio de control estricto de existencias, transaccionalidad y auditoría (Kárdex)."""

    @classmethod
    def record_movement(cls, product: Product, user_id: int, movement_type: str, quantity: int, reason: str, reference_id: str = None) -> InventoryMovement:
        """Registra un movimiento en el kárdex auditado."""
        if quantity <= 0:
            raise ValueError("La cantidad del movimiento debe ser un número entero positivo.")

        previous_stock = product.stock

        if movement_type in [MovementType.PURCHASE_ENTRY, MovementType.ADJUSTMENT_IN, MovementType.ORDER_CANCEL_RESTORE]:
            new_stock = previous_stock + quantity
        elif movement_type in [MovementType.SALE_EXIT, MovementType.ADJUSTMENT_OUT]:
            if previous_stock < quantity:
                raise ValueError(f"No es posible realizar una salida de {quantity} unidades. Stock actual: {previous_stock}.")
            new_stock = previous_stock - quantity
        else:
            raise ValueError(f"Tipo de movimiento '{movement_type}' no reconocido.")

        product.stock = new_stock

        movement = InventoryMovement(
            product_id=product.id,
            user_id=user_id,
            movement_type=movement_type,
            quantity=quantity,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reason=reason,
            reference_id=reference_id
        )
        db.session.add(movement)
        return movement

    @classmethod
    def adjust_stock(cls, product_id: int, user_id: int, target_stock: int, reason: str) -> InventoryMovement:
        """Ajuste manual de inventario realizado por un administrador."""
        if target_stock < 0:
            raise ValueError("El nuevo stock no puede ser negativo.")

        product = Product.query.filter_by(id=product_id).with_for_update().first()
        if not product:
            raise ValueError("Producto no encontrado.")

        diff = target_stock - product.stock
        if diff == 0:
            raise ValueError("El nuevo stock es idéntico a las existencias actuales. No se requiere ajuste.")

        if diff > 0:
            movement_type = MovementType.ADJUSTMENT_IN
            qty = diff
        else:
            movement_type = MovementType.ADJUSTMENT_OUT
            qty = abs(diff)

        movement = cls.record_movement(
            product=product,
            user_id=user_id,
            movement_type=movement_type,
            quantity=qty,
            reason=reason,
            reference_id="MANUAL-ADJUSTMENT"
        )
        db.session.commit()
        return movement

    @classmethod
    def deduct_stock_for_order(cls, items_to_buy: list[dict], user_id: int, order_number: str):
        """
        Bloquea concurrentemente las filas de productos con 'with_for_update()'
        y descuenta el inventario de forma atómica.
        items_to_buy: [{'product_id': int, 'quantity': int}]
        """
        # Ordenar por product_id para evitar deadlocks en transacciones concurrentes
        sorted_items = sorted(items_to_buy, key=lambda x: x['product_id'])

        for item_data in sorted_items:
            product_id = item_data['product_id']
            qty = item_data['quantity']

            product = Product.query.filter_by(id=product_id).with_for_update().first()
            if not product or not product.is_active:
                raise ValueError(f"El producto con ID {product_id} no está disponible para la venta.")

            if product.stock < qty:
                raise InsufficientStockError(product.name, product.stock, qty)

            cls.record_movement(
                product=product,
                user_id=user_id,
                movement_type=MovementType.SALE_EXIT,
                quantity=qty,
                reason=f"Venta confirmada en pedido #{order_number}",
                reference_id=order_number
            )

    @classmethod
    def restore_stock_for_cancelled_order(cls, order: Order, user_id: int, reason: str):
        """Repone las existencias en el inventario al cancelar un pedido."""
        for item in order.items:
            product = Product.query.filter_by(id=item.product_id).with_for_update().first()
            if product:
                cls.record_movement(
                    product=product,
                    user_id=user_id,
                    movement_type=MovementType.ORDER_CANCEL_RESTORE,
                    quantity=item.quantity,
                    reason=f"Reposición por cancelación de pedido #{order.order_number}: {reason}",
                    reference_id=order.order_number
                )
