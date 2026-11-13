from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
from app.extensions import db


class PaymentStatus:
    PENDING = 'PENDING'      # Pendiente
    APPROVED = 'APPROVED'    # Aprobado en prueba
    REJECTED = 'REJECTED'    # Rechazado en prueba
    CANCELLED = 'CANCELLED'  # Cancelado

    ALL_STATUSES = [PENDING, APPROVED, REJECTED, CANCELLED]

    LABELS = {
        PENDING: 'Pendiente de pago',
        APPROVED: 'Aprobado (Modo prueba)',
        REJECTED: 'Rechazado (Modo prueba)',
        CANCELLED: 'Cancelado'
    }


class PaymentMethod:
    SIMULATED_CARD = 'SIMULATED_CARD'
    SIMULATED_TRANSFER = 'SIMULATED_TRANSFER'
    SIMULATED_CASH_ON_DELIVERY = 'SIMULATED_CASH_ON_DELIVERY'

    ALL_METHODS = [
        SIMULATED_CARD,
        SIMULATED_TRANSFER,
        SIMULATED_CASH_ON_DELIVERY
    ]

    LABELS = {
        SIMULATED_CARD: 'Tarjeta Débito/Crédito (Simulación)',
        SIMULATED_TRANSFER: 'Transferencia Bancaria (Simulación)',
        SIMULATED_CASH_ON_DELIVERY: 'Contraentrega (Simulación)'
    }


class Payment(db.Model):
    """Registro de transacciones de pago en modo de prueba sin cobros reales."""
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='RESTRICT'), nullable=False, index=True)
    transaction_reference = db.Column(db.String(100), unique=True, nullable=False, index=True)
    payment_method = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(30), default=PaymentStatus.PENDING, nullable=False, index=True)
    is_simulation = db.Column(db.Boolean, default=True, nullable=False)  # Siempre True en etapa inicial
    gateway_response_raw = db.Column(db.Text, nullable=True)  # JSON serializado con respuesta simulada
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.Index('ix_payments_order_status', 'order_id', 'status'),

        db.CheckConstraint('amount >= 0', name='check_payment_amount_positive'),
        db.CheckConstraint(
            f"status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name='check_payment_status_valid'
        )
    )

    order = db.relationship('Order', back_populates='payments')

    @property
    def status_label(self) -> str:
        return PaymentStatus.LABELS.get(self.status, self.status)

    @property
    def method_label(self) -> str:
        return PaymentMethod.LABELS.get(self.payment_method, self.payment_method)

    @property
    def gateway_response(self) -> dict:
        if self.gateway_response_raw:
            try:
                value = json.loads(self.gateway_response_raw)
                if isinstance(value, dict):
                    return value
                logging.getLogger(__name__).warning("Respuesta de pago %s con tipo inesperado", self.id)
            except (json.JSONDecodeError, TypeError):
                logging.getLogger(__name__).warning("Respuesta de pago %s con JSON inválido", self.id)
        return {}

    @gateway_response.setter
    def gateway_response(self, value: dict):
        self.gateway_response_raw = json.dumps(value)

    def __repr__(self):
        return f"<Payment Ref:{self.transaction_reference} Status:{self.status} Amount:${self.amount}>"
