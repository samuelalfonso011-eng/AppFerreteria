import pytest
from decimal import Decimal
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.payment_service import payment_service


def test_26_27_28_29_payment_simulation_states_and_safety(app):
    """Criterios 26 a 30: Simulación de pago con resultados aprobados, rechazados, pendientes y sin datos de tarjetas."""
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        prod = Product.query.get(1)

        CartService.add_item(product_id=prod.id, quantity=1, user=user)
        order = OrderService.create_order(
            user=user,
            shipping_data={
                'recipient_name': 'Juan Perez',
                'phone': '3001234567',
                'department': 'Antioquia',
                'city': 'Medellín',
                'neighborhood': 'Laureles',
                'street_address': 'Circular 4 # 73-20'
            }
        )

        # 1. Simulación Rechazada
        payment_rejected = payment_service.process_payment(
            order=order,
            payment_method=PaymentMethod.SIMULATED_CARD,
            simulated_action='reject'
        )
        assert payment_rejected.status == PaymentStatus.REJECTED
        assert payment_rejected.is_simulation is True
        assert order.status == OrderStatus.PENDING_CONFIRMATION  # Sigue pendiente

        # 2. Simulación Pendiente
        payment_pending = payment_service.process_payment(
            order=order,
            payment_method=PaymentMethod.SIMULATED_TRANSFER,
            simulated_action='pending'
        )
        assert payment_pending.status == PaymentStatus.PENDING
        assert payment_pending.is_simulation is True

        # 3. Simulación Aprobada
        payment_approved = payment_service.process_payment(
            order=order,
            payment_method=PaymentMethod.SIMULATED_CARD,
            simulated_action='approve'
        )
        assert payment_approved.status == PaymentStatus.APPROVED
        assert payment_approved.is_simulation is True
        # El pedido cambia a CONFIRMED automáticamente en el servidor
        assert order.status == OrderStatus.CONFIRMED

        # Criterio 29: El modelo Payment no contiene columnas de CVV, expiración ni números de tarjeta
        column_names = [c.name for c in Payment.__table__.columns]
        assert 'cvv' not in column_names
        assert 'card_number' not in column_names
        assert 'expiration_date' not in column_names
