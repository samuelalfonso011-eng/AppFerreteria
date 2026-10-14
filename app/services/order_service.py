from datetime import datetime, timezone
from decimal import Decimal
import uuid
from app.extensions import db
from app.models.order import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.models.setting import StoreSetting
from app.services.cart_service import CartService
from app.services.inventory_service import InventoryService, InsufficientStockError


class OrderService:
    """Servicio transaccional de gestión de pedidos, compras e historial."""

    @classmethod
    def generate_order_number(cls) -> str:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f"ORD-{date_str}-{random_suffix}"

    @classmethod
    def create_order(
        cls,
        user,
        shipping_data: dict,
        idempotency_key: str = None,
        notes: str = None
    ) -> Order:
        """
        Crea un pedido transaccional atómico:
        1. Valida clave de idempotencia para prevenir duplicados.
        2. Bloquea y descuenta existencias en el inventario.
        3. Fija snapshots históricos de precios y dirección.
        4. Vacía el carrito del usuario.
        """
        # 1. Protección de Idempotencia
        if idempotency_key:
            existing_order = Order.query.filter_by(idempotency_key=idempotency_key).first()
            if existing_order:
                return existing_order

        # 2. Obtener datos vigentes del carrito
        cart_data = CartService.get_cart_data(user)
        items = cart_data['items']
        if not items:
            raise ValueError("No se puede crear un pedido con el carrito vacío.")

        # Verificar disponibilidad antes de iniciar transacción
        items_to_deduct = [{'product_id': it['product_id'], 'quantity': it['quantity']} for it in items]

        order_number = cls.generate_order_number()
        settings = StoreSetting.get_settings()
        subtotal = cart_data['subtotal']
        shipping_cost = settings.calculate_shipping(subtotal)
        total = subtotal + shipping_cost

        # 3. Transacción atómica
        try:
            # Descontar existencias concurrentemente con bloqueo pesimista
            InventoryService.deduct_stock_for_order(items_to_deduct, user.id, order_number)

            # Crear la orden principal con snapshots históricos inmutables
            order = Order(
                order_number=order_number,
                user_id=user.id,
                status=OrderStatus.PENDING_CONFIRMATION,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total=total,
                idempotency_key=idempotency_key,
                shipping_recipient_name=shipping_data['recipient_name'],
                shipping_phone=shipping_data['phone'],
                shipping_department=shipping_data['department'],
                shipping_city=shipping_data['city'],
                shipping_neighborhood=shipping_data['neighborhood'],
                shipping_street_address=shipping_data['street_address'],
                shipping_complement=shipping_data.get('complement'),
                shipping_instructions=shipping_data.get('delivery_instructions'),
                notes=notes
            )
            db.session.add(order)
            db.session.flush()  # Obtener ID de la orden

            # Registrar líneas de orden con precios históricos congelados
            for it in items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=it['product_id'],
                    product_name=it['name'],
                    product_sku=it['sku'],
                    unit_price=it['price'],
                    quantity=it['quantity'],
                    subtotal=it['subtotal']
                )
                db.session.add(order_item)

            # Historial inicial
            history = OrderStatusHistory(
                order_id=order.id,
                previous_status=None,
                new_status=OrderStatus.PENDING_CONFIRMATION,
                changed_by_user_id=user.id,
                comment="Pedido registrado por el cliente."
            )
            db.session.add(history)

            # Vaciar carrito tras la confirmación exitosa
            CartService.clear_cart(user)

            db.session.commit()
            return order

        except Exception as e:
            db.session.rollback()
            raise e

    @classmethod
    def change_order_status(cls, order_id: int, new_status: str, changed_by_user_id: int, comment: str = None) -> Order:
        """
        Actualiza el estado de un pedido validando las transiciones autorizadas de la máquina de estados.
        Si se cancela, repone las existencias en el inventario.
        """
        order = Order.query.filter_by(id=order_id).with_for_update().first()
        if not order:
            raise ValueError("Pedido no encontrado.")

        if new_status == order.status:
            return order

        allowed = OrderStatus.VALID_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            raise ValueError(f"Transición no permitida de '{order.status_label}' a '{OrderStatus.LABELS.get(new_status, new_status)}'.")

        prev_status = order.status
        order.status = new_status
        order.updated_at = datetime.now(timezone.utc)

        # Si se cancela el pedido, reponer inventario en el kárdex
        if new_status == OrderStatus.CANCELLED:
            InventoryService.restore_stock_for_cancelled_order(
                order=order,
                user_id=changed_by_user_id,
                reason=comment or "Cancelación de pedido"
            )

        history = OrderStatusHistory(
            order_id=order.id,
            previous_status=prev_status,
            new_status=new_status,
            changed_by_user_id=changed_by_user_id,
            comment=comment
        )
        db.session.add(history)
        db.session.commit()
        return order

    @classmethod
    def cancel_by_customer(cls, order_id: int, customer_user_id: int, reason: str = None) -> Order:
        """Permite al cliente cancelar su propio pedido si aún está en estado previo a preparación."""
        order = Order.query.filter_by(id=order_id, user_id=customer_user_id).first()
        if not order:
            raise ValueError("Pedido no encontrado.")

        if not order.can_cancel_by_customer:
            raise ValueError("El pedido ya está en preparación o envío y no puede cancelarse desde su perfil.")

        return cls.change_order_status(
            order_id=order.id,
            new_status=OrderStatus.CANCELLED,
            changed_by_user_id=customer_user_id,
            comment=f"Cancelado por el cliente: {reason or 'Sin motivo especificado'}"
        )
