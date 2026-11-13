from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class OrderStatus:
    PENDING_CONFIRMATION = 'PENDING_CONFIRMATION'  # Pendiente de confirmación
    CONFIRMED = 'CONFIRMED'                        # Confirmado / Pago aprobado
    PREPARING = 'PREPARING'                        # En preparación en bodega
    SHIPPED = 'SHIPPED'                            # En ruta de entrega
    DELIVERED = 'DELIVERED'                        # Entregado al cliente
    CANCELLED = 'CANCELLED'                        # Cancelado

    ALL_STATUSES = [
        PENDING_CONFIRMATION,
        CONFIRMED,
        PREPARING,
        SHIPPED,
        DELIVERED,
        CANCELLED
    ]

    # Transiciones válidas de estado en la máquina de estados del pedido
    VALID_TRANSITIONS = {
        PENDING_CONFIRMATION: [CONFIRMED, CANCELLED],
        CONFIRMED: [PREPARING, CANCELLED],
        PREPARING: [SHIPPED, CANCELLED],
        SHIPPED: [DELIVERED, CANCELLED],
        DELIVERED: [],
        CANCELLED: []
    }

    # Nombres amigables para la UI
    LABELS = {
        PENDING_CONFIRMATION: 'Pendiente de confirmación',
        CONFIRMED: 'Confirmado',
        PREPARING: 'En preparación',
        SHIPPED: 'Enviado',
        DELIVERED: 'Entregado',
        CANCELLED: 'Cancelado'
    }


class Order(db.Model):
    """Modelo principal de pedidos con snapshots históricos inmutables."""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    status = db.Column(db.String(30), default=OrderStatus.PENDING_CONFIRMATION, nullable=False, index=True)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    shipping_cost = db.Column(db.Numeric(12, 2), default=Decimal('0.00'), nullable=False)
    total = db.Column(db.Numeric(12, 2), nullable=False)
    idempotency_key = db.Column(db.String(100), unique=True, nullable=True, index=True)

    # Snapshot inmutable de la dirección de entrega al momento de comprar
    shipping_recipient_name = db.Column(db.String(150), nullable=False)
    shipping_phone = db.Column(db.String(30), nullable=False)
    shipping_department = db.Column(db.String(100), nullable=False)
    shipping_city = db.Column(db.String(100), nullable=False)
    shipping_neighborhood = db.Column(db.String(100), nullable=False)
    shipping_street_address = db.Column(db.String(255), nullable=False)
    shipping_complement = db.Column(db.String(100), nullable=True)
    shipping_instructions = db.Column(db.Text, nullable=True)

    # Datos para Facturación Electrónica DIAN
    fiscal_doc_type = db.Column(db.String(20), default='CC', nullable=True)
    fiscal_doc_number = db.Column(db.String(50), nullable=True)
    fiscal_name = db.Column(db.String(150), nullable=True)
    fiscal_email = db.Column(db.String(150), nullable=True)

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.Index('ix_orders_user_created', 'user_id', 'created_at'),
        db.Index('ix_orders_status_created', 'status', 'created_at'),

        db.CheckConstraint('subtotal >= 0', name='check_order_subtotal_positive'),
        db.CheckConstraint('shipping_cost >= 0', name='check_order_shipping_positive'),
        db.CheckConstraint('total >= 0', name='check_order_total_positive'),
        db.CheckConstraint(
            f"status IN ('PENDING_CONFIRMATION', 'CONFIRMED', 'PREPARING', 'SHIPPED', 'DELIVERED', 'CANCELLED')",
            name='check_order_status_valid'
        )
    )

    # Relaciones
    user = db.relationship('User', back_populates='orders')
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan', lazy='joined')
    payments = db.relationship('Payment', back_populates='order', cascade='all, delete-orphan', lazy='dynamic')
    status_history = db.relationship('OrderStatusHistory', back_populates='order', cascade='all, delete-orphan', order_by='OrderStatusHistory.created_at.asc()')
    invoice = db.relationship('ElectronicInvoice', back_populates='order', uselist=False, cascade='all, delete-orphan')

    @property
    def status_label(self) -> str:
        """Devuelve el nombre legible del estado."""
        return OrderStatus.LABELS.get(self.status, self.status)

    @property
    def status_code(self) -> str:
        """Alias para status."""
        return self.status

    @property
    def can_cancel_by_customer(self) -> bool:
        """Regla de negocio: el cliente solo puede cancelar antes de entrar a preparación."""
        return self.status in [OrderStatus.PENDING_CONFIRMATION, OrderStatus.CONFIRMED]

    @property
    def latest_payment(self):
        """Devuelve el último intento de pago registrado para este pedido."""
        from app.models.payment import Payment
        return self.payments.order_by(Payment.created_at.desc()).first()

    @property
    def payment(self):
        """Alias de compatibilidad para el último pago registrado."""
        return self.latest_payment

    @property
    def all_payments(self):
        """Devuelve la lista de pagos ordenados de forma descendente por fecha."""
        from app.models.payment import Payment
        return self.payments.order_by(Payment.created_at.desc()).all()

    @property
    def order_items(self):
        """Alias de compatibilidad para self.items."""
        return self.items

    @property
    def customer(self):
        """Alias de compatibilidad para self.user."""
        return self.user

    def formatted_shipping_address(self) -> str:
        parts = [self.shipping_street_address]
        if self.shipping_complement:
            parts.append(self.shipping_complement)
        parts.extend([self.shipping_neighborhood, self.shipping_city, self.shipping_department])
        return ", ".join(parts)

    def __repr__(self):
        return f"<Order {self.order_number} - Status: {self.status} - Total: ${self.total}>"


class OrderItem(db.Model):
    """Líneas de detalle de una orden con preservación histórica del precio unitario."""
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_sku = db.Column(db.String(50), nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)

    __table_args__ = (
        db.CheckConstraint('unit_price >= 0', name='check_item_unit_price_positive'),
        db.CheckConstraint('quantity > 0', name='check_item_quantity_positive'),
        db.CheckConstraint('subtotal >= 0', name='check_item_subtotal_positive'),
    )

    order = db.relationship('Order', back_populates='items')
    product = db.relationship('Product', back_populates='order_items')

    def __repr__(self):
        return f"<OrderItem Order:{self.order_id} SKU:{self.product_sku} Qty:{self.quantity}>"


class OrderStatusHistory(db.Model):
    """Trazabilidad y auditoría de cambios de estado del pedido."""
    __tablename__ = 'order_status_history'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, index=True)
    previous_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=False)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    order = db.relationship('Order', back_populates='status_history')
    changed_by = db.relationship('User')

    def __repr__(self):
        return f"<OrderStatusHistory Order:{self.order_id} {self.previous_status} -> {self.new_status}>"
