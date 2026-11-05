import pytest
from decimal import Decimal
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderStatus
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.payment_service import payment_service


def login_admin(client):
    client.post('/login', data={
        'email': 'admin@ferreteria.com',
        'password': 'AdminPass123*'
    }, follow_redirects=True)


def test_31_32_dashboard_queries_real_database_metrics(client, app):
    """Criterios 31 y 32: El dashboard consulta datos reales de PostgreSQL y excluye cancelados de ventas confirmadas."""
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        prod = Product.query.get(1)

        # Pedido 1: Confirmado con pago aprobado ($35,000)
        CartService.add_item(prod.id, 1, user)
        o1 = OrderService.create_order(
            user=user,
            shipping_data={'recipient_name': 'Juan', 'phone': '300', 'department': 'Ant', 'city': 'Med', 'neighborhood': 'L', 'street_address': 'C1'}
        )
        payment_service.process_payment(o1, 'SIMULATED_CARD', 'approve')

        # Pedido 2: Cancelado ($35,000)
        CartService.add_item(prod.id, 1, user)
        o2 = OrderService.create_order(
            user=user,
            shipping_data={'recipient_name': 'Juan', 'phone': '300', 'department': 'Ant', 'city': 'Med', 'neighborhood': 'L', 'street_address': 'C1'}
        )
        OrderService.cancel_by_customer(o2.id, user.id, "Cancelación")

    login_admin(client)
    response = client.get('/admin/')
    assert response.status_code == 200

    # Ventas confirmadas deben reflejar únicamente el pedido 1 ($35,000) y excluir el pedido cancelado
    # Formato COP sin decimales: $ 35.000\n    assert "35.000".encode('utf-8') in response.data and "35.000,00".encode('utf-8') not in response.data


def test_34_order_state_transitions(app):
    """Criterio 34: La máquina de estados de pedidos valida las transiciones válidas y rechaza transiciones ilegales."""
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        prod = Product.query.get(1)

        CartService.add_item(prod.id, 1, user)
        order = OrderService.create_order(
            user=user,
            shipping_data={'recipient_name': 'Juan', 'phone': '300', 'department': 'Ant', 'city': 'Med', 'neighborhood': 'L', 'street_address': 'C1'}
        )
        assert order.status == OrderStatus.PENDING_CONFIRMATION

        # Transición válida: PENDING -> CONFIRMED
        OrderService.change_order_status(order.id, OrderStatus.CONFIRMED, changed_by_user_id=1)
        assert order.status == OrderStatus.CONFIRMED

        # Transición válida: CONFIRMED -> PREPARING
        OrderService.change_order_status(order.id, OrderStatus.PREPARING, changed_by_user_id=1)
        assert order.status == OrderStatus.PREPARING

        # Transición INVÁLIDA: PREPARING -> DELIVERED (no se puede saltar SHIPPED)
        with pytest.raises(ValueError):
            OrderService.change_order_status(order.id, OrderStatus.DELIVERED, changed_by_user_id=1)


def test_35_unauthorized_users_cannot_execute_admin_operations(client):
    """Criterio 35: Usuarios no autorizados no pueden ejecutar operaciones administrativas."""
    # Intentar crear producto sin autenticación
    res = client.post('/admin/productos/crear', data={'name': 'Hack'}, follow_redirects=True)
    assert res.status_code == 200
    assert "iniciar sesión con una cuenta de administrador".encode('utf-8') in res.data or "Iniciar Sesión".encode('utf-8') in res.data
