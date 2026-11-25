from app.extensions import db
from app.utils.timeutils import iso, utcnow


class MovementType:
    PURCHASE_ENTRY = "PURCHASE_ENTRY"            # Entrada por compra a proveedor
    SALE_EXIT = "SALE_EXIT"                      # Salida por venta
    ADJUSTMENT_IN = "ADJUSTMENT_IN"              # Ajuste positivo
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"            # Ajuste negativo (merma, dano, faltante)
    ORDER_CANCEL_RESTORE = "ORDER_CANCEL_RESTORE"  # Reposicion por pedido cancelado

    ALL = (PURCHASE_ENTRY, SALE_EXIT, ADJUSTMENT_IN, ADJUSTMENT_OUT, ORDER_CANCEL_RESTORE)
    MANUAL = (PURCHASE_ENTRY, ADJUSTMENT_IN, ADJUSTMENT_OUT)
    INCREASES = (PURCHASE_ENTRY, ADJUSTMENT_IN, ORDER_CANCEL_RESTORE)

    LABELS = {
        PURCHASE_ENTRY: "Entrada por compra",
        SALE_EXIT: "Salida por venta",
        ADJUSTMENT_IN: "Ajuste positivo",
        ADJUSTMENT_OUT: "Ajuste negativo",
        ORDER_CANCEL_RESTORE: "Reposicion por cancelacion",
    }


class InventoryMovement(db.Model):
    """Kardex: cada cambio de stock deja un registro inmutable."""
    __tablename__ = "inventory_movements"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    movement_type = db.Column(db.String(30), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    previous_stock = db.Column(db.Integer, nullable=False)
    new_stock = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    reference = db.Column(db.String(100), index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="check_movement_quantity"),
        db.CheckConstraint("new_stock >= 0", name="check_movement_new_stock"),
        db.CheckConstraint(
            "movement_type IN ('PURCHASE_ENTRY', 'SALE_EXIT', 'ADJUSTMENT_IN', "
            "'ADJUSTMENT_OUT', 'ORDER_CANCEL_RESTORE')",
            name="check_movement_type",
        ),
    )

    product = db.relationship("Product", back_populates="movements")
    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.movement_type,
            "type_label": MovementType.LABELS.get(self.movement_type, self.movement_type),
            "quantity": self.quantity,
            "previous_stock": self.previous_stock,
            "new_stock": self.new_stock,
            "reason": self.reason,
            "reference": self.reference,
            "user": self.user.full_name if self.user else None,
            "created_at": iso(self.created_at),
        }
