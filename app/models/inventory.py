from datetime import datetime, timezone
from app.extensions import db


class MovementType:
    PURCHASE_ENTRY = 'PURCHASE_ENTRY'            # Entrada por compra / recepción de proveedor
    SALE_EXIT = 'SALE_EXIT'                      # Salida por venta confirmada
    ADJUSTMENT_IN = 'ADJUSTMENT_IN'              # Ajuste positivo de inventario
    ADJUSTMENT_OUT = 'ADJUSTMENT_OUT'            # Ajuste negativo (mermas, daño, faltante)
    ORDER_CANCEL_RESTORE = 'ORDER_CANCEL_RESTORE' # Reposición por pedido cancelado

    ALL_TYPES = [
        PURCHASE_ENTRY,
        SALE_EXIT,
        ADJUSTMENT_IN,
        ADJUSTMENT_OUT,
        ORDER_CANCEL_RESTORE
    ]


class InventoryMovement(db.Model):
    """Kárdex de movimientos de inventario auditados y trazables."""
    __tablename__ = 'inventory_movements'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    movement_type = db.Column(db.String(30), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    previous_stock = db.Column(db.Integer, nullable=False)
    new_stock = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    reference_id = db.Column(db.String(100), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        db.CheckConstraint('quantity > 0', name='check_positive_movement_quantity'),
        db.CheckConstraint('previous_stock >= 0', name='check_non_negative_prev_stock'),
        db.CheckConstraint('new_stock >= 0', name='check_non_negative_new_stock'),
        db.CheckConstraint(
            f"movement_type IN ('PURCHASE_ENTRY', 'SALE_EXIT', 'ADJUSTMENT_IN', 'ADJUSTMENT_OUT', 'ORDER_CANCEL_RESTORE')",
            name='check_valid_movement_type'
        )
    )

    product = db.relationship('Product', back_populates='inventory_movements')
    user = db.relationship('User')

    def __repr__(self):
        return f"<InventoryMovement {self.movement_type} - Prod {self.product_id} - Qty: {self.quantity}>"
