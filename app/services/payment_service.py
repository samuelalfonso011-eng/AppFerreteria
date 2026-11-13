from sqlalchemy.orm import lazyload
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
import uuid
from app.extensions import db
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.order import Order, OrderStatus, OrderStatusHistory


class BasePaymentProvider(ABC):
    """Interfaz base para proveedores de pago (preparada para futuras pasarelas reales)."""

    @abstractmethod
    def process_payment(self, order: Order, payment_method: str, simulated_action: str = 'approve') -> Payment:
        pass


class SimulatedPaymentProvider(BasePaymentProvider):
    """
    Proveedor de pago en MODO DE PRUEBA.
    No solicita números reales de tarjeta, no realiza cobros monetarios,
    y permite probar de forma determinista y segura los flujos comerciales
    de pago aprobado, rechazado y pendiente.
    """

    def process_payment(self, order: Order, payment_method: str, simulated_action: str = 'approve', idempotency_key: str = None) -> Payment:
        from flask import current_app
        if not current_app.config.get('PAYMENTS_SIMULATION_ENABLED', False):
            raise ValueError("Los pagos de prueba están deshabilitados en este entorno.")

        # Bloqueo de fila para serializar pagos concurrentes sobre el mismo pedido
        locked = Order.query.options(lazyload(Order.items)).filter_by(id=order.id).populate_existing().with_for_update(of=Order).first()
        if locked is not None:
            order = locked

        # Prevención estricta de doble pago: si ya existe pago aprobado, retornar de inmediato
        existing_approved = order.payments.filter_by(status=PaymentStatus.APPROVED).first()
        if existing_approved:
            return existing_approved

        # Prevención por llave de idempotencia
        if idempotency_key:
            for p in order.payments:
                if p.gateway_response.get("idempotency_key") == idempotency_key:
                    return p

        if order.status != OrderStatus.PENDING_CONFIRMATION:
            raise ValueError("Este pedido ya no admite pagos (cancelado o ya procesado).")

        if payment_method not in PaymentMethod.ALL_METHODS:
            raise ValueError(f"Método de pago no válido: {payment_method}")

        now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        ref = f"SIM-{order.id}-{now_str}-{uuid.uuid4().hex[:6].upper()}"

        # Mapeo de la acción simulada al estado de pago
        action = (simulated_action or 'approve').lower().strip()
        if action == 'approve':
            status = PaymentStatus.APPROVED
            response_msg = "Transacción simulada aprobada exitosamente."
        elif action == 'reject':
            status = PaymentStatus.REJECTED
            response_msg = "Transacción simulada declinada por fondos insuficientes o rechazo simulado."
        elif action == 'pending':
            status = PaymentStatus.PENDING
            response_msg = "Transacción simulada en espera de confirmación de red."
        else:
            raise ValueError(f"Acción de simulación no soportada: {simulated_action}")

        payment = Payment(
            order_id=order.id,
            transaction_reference=ref,
            payment_method=payment_method,
            amount=order.total,
            status=status,
            is_simulation=True
        )
        payment.gateway_response = {
            "mode": "SIMULATION",
            "message": response_msg,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "simulation_code": "00" if status == PaymentStatus.APPROVED else "05",
            "idempotency_key": idempotency_key
        }
        db.session.add(payment)

        # Si el pago es aprobado, actualizar el pedido a CONFIRMED y generar Factura Electrónica
        if status == PaymentStatus.APPROVED:
            prev_status = order.status
            order.status = OrderStatus.CONFIRMED
            order.updated_at = datetime.now(timezone.utc)

            history = OrderStatusHistory(
                order_id=order.id,
                previous_status=prev_status,
                new_status=OrderStatus.CONFIRMED,
                comment=f"Pago de prueba aprobado con ref: {ref}"
            )
            db.session.add(history)
            db.session.commit()

            # Generar automáticamente la Factura Electrónica DIAN
            from app.services.invoice_service import InvoiceService
            try:
                InvoiceService.get_or_create_invoice_for_order(order)
            except Exception:
                db.session.rollback()
                import logging
                logging.getLogger(__name__).exception("Fallo al generar la factura del pedido %s", order.order_number)
        else:
            db.session.commit()

        return payment


# Instancia por defecto para la primera fase
payment_service = SimulatedPaymentProvider()


class PaymentService:
    """Fachada estática para servicios de procesamiento de pagos."""

    @staticmethod
    def process_payment(order: Order, payment_method: str, simulated_action: str = 'approve', idempotency_key: str = None) -> Payment:
        return payment_service.process_payment(
            order=order,
            payment_method=payment_method,
            simulated_action=simulated_action,
            idempotency_key=idempotency_key
        )

