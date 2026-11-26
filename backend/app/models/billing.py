from app.extensions import db
from app.utils.timeutils import iso, utcnow

PAYMENT_METHODS = ("efectivo", "tarjeta", "transferencia", "pse", "nequi")


class Invoice(db.Model):
    __tablename__ = "invoices"
    __table_args__ = (
        db.UniqueConstraint("id", "order_id", name="uq_invoice_id_order"),
        db.CheckConstraint("status IN ('emitida', 'anulada')", name="check_invoice_status"),
        db.CheckConstraint(
            "subtotal >= 0 AND shipping_cost >= 0 AND tax_amount >= 0 "
            "AND discount_amount BETWEEN 0 AND subtotal "
            "AND total_amount = round(subtotal + shipping_cost + tax_amount - discount_amount, 2)",
            name="check_invoice_amounts",
        ),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.Integer, db.Computed("id", persisted=True), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, unique=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    subtotal = db.Column(db.Numeric(14, 2), nullable=False)
    shipping_cost = db.Column(db.Numeric(14, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(14, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(14, 2), nullable=False)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="emitida", server_default="emitida")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    items = db.relationship("InvoiceItem", order_by="InvoiceItem.id", lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id, "invoice_number": self.invoice_number, "order_id": self.order_id,
            "employee_id": self.employee_id, "status": self.status, "created_at": iso(self.created_at),
            "subtotal": str(self.subtotal), "shipping_cost": str(self.shipping_cost),
            "tax_amount": str(self.tax_amount), "discount_amount": str(self.discount_amount),
            "total_amount": str(self.total_amount), "items": [item.to_dict() for item in self.items],
        }


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0 AND unit_price >= 0 AND subtotal = round(quantity * unit_price, 2)",
                           name="check_invoice_item_amounts"),
    )

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    sku = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(14, 2), nullable=False)
    subtotal = db.Column(db.Numeric(14, 2), nullable=False)

    def to_dict(self):
        return {
            "product_id": self.product_id, "name": self.name, "sku": self.sku, "quantity": self.quantity,
            "unit_price": str(self.unit_price), "subtotal": str(self.subtotal),
        }


class Payment(db.Model):
    __tablename__ = "payments"
    __table_args__ = (
        db.ForeignKeyConstraint(["invoice_id", "order_id"], ["invoices.id", "invoices.order_id"]),
        db.CheckConstraint("amount > 0", name="check_payment_amount"),
        db.CheckConstraint("payment_method IN ('efectivo', 'tarjeta', 'transferencia', 'pse', 'nequi')",
                           name="check_payment_method"),
        db.CheckConstraint("status IN ('pendiente', 'aprobado', 'rechazado', 'anulado')",
                           name="check_payment_status"),
        db.CheckConstraint(
            "(receipt_data IS NULL AND receipt_type IS NULL) OR "
            "(receipt_data IS NOT NULL AND receipt_type IS NOT NULL "
            "AND receipt_type IN ('application/pdf', 'image/png', 'image/jpeg') "
            "AND length(receipt_data) BETWEEN 1 AND 5242880)", name="check_payment_receipt",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    payment_method = db.Column(db.String(15), nullable=False)
    receipt_type = db.Column(db.String(20))
    receipt_data = db.deferred(db.Column(db.LargeBinary))
    receipt_path = db.Column(db.Text, db.Computed(
        "CASE WHEN receipt_type IS NOT NULL THEN '/api/payments/' || CAST(id AS TEXT) || '/receipt' END",
        persisted=True,
    ))
    status = db.Column(db.String(10), nullable=False)
    paid_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id, "invoice_id": self.invoice_id, "order_id": self.order_id,
            "amount": str(self.amount), "payment_method": self.payment_method, "status": self.status,
            "paid_at": iso(self.paid_at), "created_at": iso(self.created_at),
            "receipt_url": self.receipt_path,
        }
