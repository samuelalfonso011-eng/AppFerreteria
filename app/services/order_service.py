from sqlalchemy.orm import lazyload
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
        notes: str = None,
        fiscal_data: dict = None,
        privacy_authorized: bool = False
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
                if existing_order.user_id != user.id:
                    raise ValueError("Clave de pedido inválida para este usuario.")
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

            f_data = fiscal_data or {}
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
                shipping_department=shipping_data.get('department') or 'Antioquia',
                shipping_city=shipping_data['city'],
                shipping_neighborhood=shipping_data['neighborhood'],
                shipping_street_address=shipping_data['street_address'],
                shipping_complement=shipping_data.get('complement'),
                shipping_instructions=shipping_data.get('delivery_instructions'),
                fiscal_doc_type=f_data.get('fiscal_doc_type', 'CC'),
                fiscal_doc_number=f_data.get('fiscal_doc_number') or '',
                fiscal_name=f_data.get('fiscal_name') or shipping_data['recipient_name'],
                fiscal_email=f_data.get('fiscal_email') or user.email,
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
            if privacy_authorized:
                from app.models.consent import record_consent
                record_consent('checkout', user_id=user.id, order_id=order.id)
            CartService.clear_cart(user, commit=False)

            db.session.commit()
            return order

        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def change_order_status(cls, order_id: int, new_status: str, changed_by_user_id: int, comment: str = None) -> Order:
        """
        Actualiza el estado de un pedido validando las transiciones autorizadas de la máquina de estados.
        Si se cancela, repone las existencias en el inventario.
        """
        order = Order.query.options(lazyload(Order.items)).filter_by(id=order_id).populate_existing().with_for_update(of=Order).first()
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
    def expire_stale_pending_orders(cls, minutes: int = None) -> int:
        """
        Cancela los pedidos que siguen en PENDING_CONFIRMATION pasado el plazo y repone su stock.
        El stock se reserva al crear el pedido; sin vencimiento, un pedido abandonado lo retendría para siempre.
        Se omiten pedidos con un pago en estado PENDING (en validación). Devuelve cuántos venció.
        """
        from datetime import timedelta
        from flask import current_app
        from app.models.payment import Payment, PaymentStatus

        if minutes is None:
            minutes = int(current_app.config.get('ORDER_PENDING_EXPIRY_MINUTES', 60))
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        has_pending_payment = db.session.query(Payment.id).filter(
            Payment.order_id == Order.id, Payment.status == PaymentStatus.PENDING
        ).exists()
        stale_ids = [
            row[0] for row in db.session.query(Order.id).filter(
                Order.status == OrderStatus.PENDING_CONFIRMATION,
                Order.created_at < cutoff,
                ~has_pending_payment
            ).all()
        ]

        expired = 0
        for order_id in stale_ids:
            try:
                order = Order.query.options(lazyload(Order.items)).filter_by(id=order_id)\
                    .populate_existing().with_for_update(of=Order).first()
                if not order or order.status != OrderStatus.PENDING_CONFIRMATION or order.payments.filter(
                    Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.APPROVED])).first():
                    db.session.rollback()
                    continue
                cls.change_order_status(
                    order_id=order_id,
                    new_status=OrderStatus.CANCELLED,
                    changed_by_user_id=order.user_id,
                    comment=f"Pedido vencido automáticamente: sin pago tras {minutes} minutos."
                )
                expired += 1
            except ValueError:
                db.session.rollback()  # cambió de estado en paralelo (p. ej. fue pagado): se omite
        return expired

    @classmethod
    def maybe_expire_stale_orders(cls, every_seconds: int = 60):
        """Ejecuta el vencimiento como máximo una vez por intervalo (sin necesidad de un cron)."""
        from app.utils.cache import cache
        if cache.get('maintenance:order_expiry:last_run'):
            return
        cache.set('maintenance:order_expiry:last_run', True, ttl=every_seconds)
        try:
            cls.expire_stale_pending_orders()
        except Exception:
            db.session.rollback()
            import logging
            logging.getLogger(__name__).exception("Fallo al vencer pedidos pendientes")

    @classmethod
    def cancel_by_customer(cls, order_id: int, customer_user_id: int, reason: str = None) -> Order:
        """Permite al cliente cancelar su propio pedido si aún está en estado previo a preparación."""
        order = Order.query.options(lazyload(Order.items)).filter_by(id=order_id, user_id=customer_user_id).populate_existing().with_for_update(of=Order).first()
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

    @classmethod
    def create_manual_order(
        cls,
        admin_user,
        customer_user,
        items_data: list,
        shipping_data: dict,
        initial_status: str = OrderStatus.CONFIRMED,
        payment_method: str = None,
        notes: str = None,
        fiscal_data: dict = None,
        is_paid: bool = True
    ) -> Order:
        """
        Crea un pedido manualmente desde el panel administrativo (ej. venta en mostrador o pedido telefónico).
        1. Valida productos activos y disponibilidad de existencias.
        2. Deduce existencias en inventario registrando la salida comercial en el kárdex.
        3. Congela snapshots históricos inmutables de precios y datos fiscales.
        4. Si initial_status está confirmado y is_paid=True, registra el pago aprobado y genera factura electrónica DIAN.
        """
        if not items_data:
            raise ValueError("No se puede generar un pedido sin productos.")

        if initial_status not in OrderStatus.ALL_STATUSES or initial_status == OrderStatus.CANCELLED:
            raise ValueError("Estado inicial de pedido no válido.")

        from app.models.product import Product
        from app.models.payment import Payment, PaymentStatus, PaymentMethod
        if is_paid and payment_method not in PaymentMethod.ALL_METHODS:
            raise ValueError("Método de pago no válido.")
        from app.services.invoice_service import InvoiceService

        # 1. Validar y procesar ítems
        product_ids = [it['product_id'] for it in items_data]
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        products_map = {p.id: p for p in products}

        parsed_items = []
        subtotal = Decimal('0.00')

        for it in items_data:
            pid = it['product_id']
            qty = int(it['quantity'])
            if qty <= 0:
                continue
            product = products_map.get(pid)
            if not product:
                raise ValueError(f"Producto con ID {pid} no encontrado.")
            if not product.is_active:
                raise ValueError(f"El producto '{product.name}' está inactivo.")
            if product.stock < qty:
                raise ValueError(f"Existencias insuficientes para '{product.name}'. Solicitado: {qty}, Disponible: {product.stock}.")

            item_subtotal = Decimal(str(product.price)) * qty
            subtotal += item_subtotal
            parsed_items.append({
                'product': product,
                'quantity': qty,
                'unit_price': Decimal(str(product.price)),
                'subtotal': item_subtotal
            })

        if not parsed_items:
            raise ValueError("Debes especificar al menos un producto con cantidad válida.")

        # 2. Costo de envío
        settings = StoreSetting.get_settings()
        shipping_type = shipping_data.get('shipping_type', 'delivery')
        if shipping_type == 'pickup':
            shipping_cost = Decimal('0.00')
        else:
            shipping_cost = settings.calculate_shipping(subtotal)
        total = subtotal + shipping_cost

        order_number = cls.generate_order_number()

        # 3. Transacción atómica
        try:
            items_to_deduct = [{'product_id': pi['product'].id, 'quantity': pi['quantity']} for pi in parsed_items]
            InventoryService.deduct_stock_for_order(items_to_deduct, admin_user.id, order_number)

            f_data = fiscal_data or {}
            target_user = customer_user or admin_user

            order = Order(
                order_number=order_number,
                user_id=target_user.id,
                status=initial_status,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total=total,
                shipping_recipient_name=shipping_data.get('recipient_name') or target_user.full_name,
                shipping_phone=shipping_data.get('phone') or target_user.phone or '',
                shipping_department=shipping_data.get('department') or 'Antioquia',
                shipping_city=shipping_data.get('city') or 'Medellín',
                shipping_neighborhood=shipping_data.get('neighborhood') or 'Centro',
                shipping_street_address=shipping_data.get('street_address') or 'Retiro en tienda',
                shipping_complement=shipping_data.get('complement'),
                shipping_instructions=shipping_data.get('delivery_instructions'),
                fiscal_doc_type=f_data.get('fiscal_doc_type', 'CC'),
                fiscal_doc_number=f_data.get('fiscal_doc_number') or '',
                fiscal_name=f_data.get('fiscal_name') or shipping_data.get('recipient_name') or target_user.full_name,
                fiscal_email=f_data.get('fiscal_email') or target_user.email,
                notes=notes
            )
            db.session.add(order)
            db.session.flush()

            for pi in parsed_items:
                p = pi['product']
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=p.id,
                    product_name=p.name,
                    product_sku=p.sku,
                    unit_price=pi['unit_price'],
                    quantity=pi['quantity'],
                    subtotal=pi['subtotal']
                )
                db.session.add(order_item)

            history = OrderStatusHistory(
                order_id=order.id,
                previous_status=None,
                new_status=initial_status,
                changed_by_user_id=admin_user.id,
                comment="Pedido generado manualmente desde el panel de administración"
            )
            db.session.add(history)

            if is_paid and payment_method:
                payment = Payment(
                    order_id=order.id,
                    transaction_reference=f"PAY-ADM-{uuid.uuid4().hex[:8].upper()}",
                    payment_method=payment_method,
                    amount=total,
                    status=PaymentStatus.APPROVED,
                    is_simulation=True,
                    gateway_response_raw='{"mode": "admin_manual_order", "status": "APPROVED", "message": "Pago registrado en panel administrativo"}'
                )
                db.session.add(payment)

            db.session.commit()

            if initial_status in [OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
                try:
                    InvoiceService.get_or_create_invoice_for_order(order)
                except Exception:
                    db.session.rollback()
                    import logging
                    logging.getLogger(__name__).exception("Fallo al generar la factura del pedido %s", order.order_number)

            return order

        except Exception:
            db.session.rollback()
            raise

