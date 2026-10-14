import pytest
from decimal import Decimal
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderStatus
from app.services.cart_service import CartService
from app.services.order_service import OrderService


def login_customer(client):
    client.post('/login', data={
        'email': 'cliente@correo.com',
        'password': 'ClientePass123*'
    }, follow_redirects=True)


def test_17_18_19_cart_calculation_and_server_price_truth(client, app):
    """Criterios 17, 18 y 19: El servidor calcula subtotales y totales; los precios del cliente se ignoran."""
    login_customer(client)

    # Agregar 2 martillos ($25,000 cada uno)
    client.post('/carrito/agregar', data={
        'product_id': 1,
        'quantity': 2,
        'price': '1.00'  # Precio manipulado maliciosamente por el cliente
    }, follow_redirects=True)

    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        cart_data = CartService.get_cart_data(user)
        # El subtotal debe ser exactamente 2 * 25,000 = 50,000 (el precio falso de 1.00 fue ignorado)
        assert cart_data['total_items'] == 2
        assert cart_data['subtotal'] == Decimal('50000.00')


def test_20_cannot_buy_more_than_available_stock(client, app):
    """Criterio 20: No se puede agregar al carrito ni comprar más de las existencias actuales."""
    login_customer(client)

    # El producto 1 tiene stock = 10
    response = client.post('/carrito/agregar', data={
        'product_id': 1,
        'quantity': 999  # Supera existencias
    }, follow_redirects=True)

    assert "unidades disponibles en existencias".encode('utf-8') in response.data


def test_21_22_23_24_order_creation_snapshots_and_idempotency(app):
    """Criterios 21, 22, 23 y 24: Pedido transaccional con snapshots de precio, descuento de stock e idempotencia."""
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        prod = Product.query.get(1)
        initial_stock = prod.stock  # 10

        # Agregar 3 unidades al carrito
        CartService.add_item(product_id=prod.id, quantity=3, user=user)

        shipping_data = {
            'recipient_name': 'Juan Perez',
            'phone': '3001234567',
            'department': 'Antioquia',
            'city': 'Medellín',
            'neighborhood': 'Laureles',
            'street_address': 'Circular 4 # 73-20',
            'complement': 'Apto 101'
        }
        idemp_key = "IDEMP-TEST-UNIQUE-12345"

        # Crear orden
        order = OrderService.create_order(
            user=user,
            shipping_data=shipping_data,
            idempotency_key=idemp_key
        )

        assert order is not None
        assert order.status == OrderStatus.PENDING_CONFIRMATION
        assert order.subtotal == Decimal('75000.00')  # 3 * 25,000
        assert order.shipping_cost == Decimal('10000.00')  # Envío estándar
        assert order.total == Decimal('85000.00')

        # Snapshot histórico de precio
        item = order.items[0]
        assert item.unit_price == Decimal('25000.00')
        assert item.product_name == "Martillo de Prueba"

        # Stock descontado: 10 - 3 = 7
        assert prod.stock == 7

        # Carrito vaciado
        cart_after = CartService.get_cart_data(user)
        assert cart_after['total_items'] == 0

        # Criterio 24: Solicitud duplicada con la misma clave de idempotencia retorna la misma orden sin descontar doble
        duplicate_order = OrderService.create_order(
            user=user,
            shipping_data=shipping_data,
            idempotency_key=idemp_key
        )
        assert duplicate_order.id == order.id
        assert prod.stock == 7  # El stock NO se volvió a debitar


def test_25_order_cancellation_restores_inventory(app):
    """Criterio 25: La cancelación de un pedido repone automáticamente las unidades en inventario."""
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        prod = Product.query.get(1)
        prev_stock = prod.stock  # 7

        # Crear un pedido de 2 unidades
        CartService.add_item(product_id=prod.id, quantity=2, user=user)
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
        assert prod.stock == prev_stock - 2  # 5

        # Cliente cancela el pedido
        OrderService.cancel_by_customer(order.id, user.id, "Compré por error")

        assert order.status == OrderStatus.CANCELLED
        # Las 2 unidades deben haberse restaurado: 5 + 2 = 7
        assert prod.stock == prev_stock
