from app.extensions import db
from app.utils.timeutils import iso, money, utcnow

DOC_TYPES = ("CC", "CE", "NIT", "PAS")


class OrderStatus:
    PENDING = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

    ALL = (PENDING, CONFIRMED, PREPARING, SHIPPED, DELIVERED, CANCELLED)
    # Estados que cuentan como venta en las metricas
    SALES = (CONFIRMED, PREPARING, SHIPPED, DELIVERED)

    TRANSITIONS = {
        PENDING: (CONFIRMED, CANCELLED),
        CONFIRMED: (PREPARING, CANCELLED),
        PREPARING: (SHIPPED, CANCELLED),
        SHIPPED: (DELIVERED, CANCELLED),
        DELIVERED: (),
        CANCELLED: (),
    }

    LABELS = {
        PENDING: "Pendiente de confirmación",
        CONFIRMED: "Confirmado",
        PREPARING: "En preparación",
        SHIPPED: "Enviado",
        DELIVERED: "Entregado",
        CANCELLED: "Cancelado",
    }


class Order(db.Model):
    """Pedido con instantaneas inmutables de cliente, direccion y precios."""
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, default=OrderStatus.PENDING, index=True)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    shipping_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(12, 2), nullable=False)
    idempotency_key = db.Column(db.String(64), unique=True)

    customer_name = db.Column(db.String(150), nullable=False)
    customer_email = db.Column(db.String(254), nullable=False, index=True)
    customer_phone = db.Column(db.String(30), nullable=False)
    doc_type = db.Column(db.String(10), nullable=False)
    doc_number = db.Column(db.String(20), nullable=False)

    department = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    neighborhood = db.Column(db.String(100), nullable=False)
    street_address = db.Column(db.String(255), nullable=False)
    complement = db.Column(db.String(100))
    notes = db.Column(db.String(500))

    # Prueba de aceptacion (Ley 1581 de 2012 y Ley 1480 de 2011)
    policy_version = db.Column(db.String(20), nullable=False)
    terms_accepted_at = db.Column(db.DateTime(timezone=True), nullable=False)
    privacy_accepted_at = db.Column(db.DateTime(timezone=True), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.Index("ix_orders_status_created", "status", "created_at"),
        db.CheckConstraint("subtotal >= 0", name="check_order_subtotal"),
        db.CheckConstraint("shipping_cost >= 0", name="check_order_shipping"),
        db.CheckConstraint("total >= 0", name="check_order_total"),
        db.CheckConstraint(
            "status IN ('PENDING_CONFIRMATION', 'CONFIRMED', 'PREPARING', 'SHIPPED', "
            "'DELIVERED', 'CANCELLED')",
            name="check_order_status",
        ),
    )

    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan",
                            lazy="selectin", order_by="OrderItem.id")
    history = db.relationship("OrderStatusHistory", back_populates="order",
                              cascade="all, delete-orphan", order_by="OrderStatusHistory.id")

    @property
    def status_label(self):
        return OrderStatus.LABELS.get(self.status, self.status)

    @property
    def address_line(self):
        parts = [self.street_address, self.complement, self.neighborhood, self.city, self.department]
        return ", ".join(p for p in parts if p)

    def _items(self):
        return [item.to_dict() for item in self.items]

    def summary(self):
        return {
            "id": self.id,
            "order_number": self.order_number,
            "status": self.status,
            "status_label": self.status_label,
            "customer_name": self.customer_name,
            "city": self.city,
            "total": money(self.total),
            "item_count": sum(item.quantity for item in self.items),
            "created_at": iso(self.created_at),
        }

    def public_view(self):
        """Lo que ve el cliente: sin documento ni direccion completa."""
        return {
            "order_number": self.order_number,
            "status": self.status,
            "status_label": self.status_label,
            "items": self._items(),
            "subtotal": money(self.subtotal),
            "shipping_cost": money(self.shipping_cost),
            "total": money(self.total),
            "city": self.city,
            "created_at": iso(self.created_at),
        }

    def admin_detail(self):
        data = self.summary()
        data.update({
            "customer": {
                "name": self.customer_name,
                "email": self.customer_email,
                "phone": self.customer_phone,
                "doc_type": self.doc_type,
                "doc_number": self.doc_number,
            },
            "shipping": {
                "department": self.department,
                "city": self.city,
                "neighborhood": self.neighborhood,
                "street_address": self.street_address,
                "complement": self.complement,
                "line": self.address_line,
            },
            "notes": self.notes,
            "items": self._items(),
            "subtotal": money(self.subtotal),
            "shipping_cost": money(self.shipping_cost),
            "consent": {
                "policy_version": self.policy_version,
                "terms_accepted_at": iso(self.terms_accepted_at),
                "privacy_accepted_at": iso(self.privacy_accepted_at),
            },
            "history": [h.to_dict() for h in self.history],
            "allowed_transitions": list(OrderStatus.TRANSITIONS.get(self.status, ())),
            "updated_at": iso(self.updated_at),
        })
        return data


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_sku = db.Column(db.String(50), nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)

    __table_args__ = (
        db.CheckConstraint("unit_price >= 0", name="check_item_price"),
        db.CheckConstraint("quantity > 0", name="check_item_quantity"),
        db.CheckConstraint("subtotal >= 0", name="check_item_subtotal"),
    )

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "name": self.product_name,
            "sku": self.product_sku,
            "unit_price": money(self.unit_price),
            "quantity": self.quantity,
            "subtotal": money(self.subtotal),
        }


class OrderStatusHistory(db.Model):
    __tablename__ = "order_status_history"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30), nullable=False)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    comment = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    order = db.relationship("Order", back_populates="history")
    changed_by = db.relationship("User")

    def to_dict(self):
        return {
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "new_status_label": OrderStatus.LABELS.get(self.new_status, self.new_status),
            "changed_by": self.changed_by.full_name if self.changed_by else "Sistema o cliente",
            "comment": self.comment,
            "created_at": iso(self.created_at),
        }
