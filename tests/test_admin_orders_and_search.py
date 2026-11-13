import pytest
from app.models.user import User, Role
from app.models.product import Product
from app.models.order import Order, OrderStatus
from app.models.invoice import ElectronicInvoice
from app.models.inventory import InventoryMovement, MovementType
from app.models.payment import PaymentMethod, PaymentStatus


def test_admin_can_access_create_order_page(app, client):
    """Verifica que el administrador puede acceder a la interfaz de creación manual de pedidos."""
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)
    resp = client.get('/admin/pedidos/nuevo')
    assert resp.status_code == 200
    assert b"Generar Nuevo Pedido" in resp.data
    assert b"Modalidad de Entrega" in resp.data
    assert b"Selecci" in resp.data or b"Art" in resp.data


def test_customer_cannot_access_create_order_page(app, client):
    """Verifica que un cliente no puede acceder a /admin/pedidos/nuevo."""
    client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}, follow_redirects=True)
    resp = client.get('/admin/pedidos/nuevo')
    assert resp.status_code in [302, 403]


def test_admin_generate_order_pickup_success(app, client):
    """Verifica la creación manual exitosa de un pedido en mostrador por parte del administrador."""
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)

    with app.app_context():
        product = Product.query.filter_by(is_active=True).first()
        initial_stock = product.stock
        prod_id = product.id

    data = {
        'shipping_type': 'pickup',
        'recipient_name': 'Carlos Rodríguez Mostrador',
        'phone': '3109876543',
        'fiscal_doc_type': 'CC',
        'fiscal_doc_number': '98765432',
        'fiscal_email': 'carlos@mostrador.com',
        f'qty_{prod_id}': '2',
        'status': OrderStatus.CONFIRMED,
        'payment_method': PaymentMethod.SIMULATED_CASH_ON_DELIVERY,
        'is_paid': '1',
        'notes': 'Venta presencial directa en caja'
    }

    resp = client.post('/admin/pedidos/nuevo', data=data, follow_redirects=True)
    assert resp.status_code == 200
    assert b"generado exitosamente" in resp.data or b"Carlos Rodr" in resp.data

    with app.app_context():
        order = Order.query.filter_by(shipping_recipient_name='Carlos Rodríguez Mostrador').first()
        assert order is not None
        assert order.status == OrderStatus.CONFIRMED
        assert order.shipping_cost == 0  # Pickup es gratis
        assert len(order.items) == 1
        assert order.items[0].quantity == 2

        # Comprobar descuento de inventario en kárdex
        updated_prod = Product.query.get(prod_id)
        assert updated_prod.stock == initial_stock - 2

        # Comprobar factura electrónica
        invoice = ElectronicInvoice.query.filter_by(order_id=order.id).first()
        assert invoice is not None
        assert invoice.invoice_number.startswith("FE-")


def test_admin_generate_order_delivery_valle_aburra(app, client):
    """Verifica la creación manual de un pedido con despacho a domicilio en Valle de Aburrá."""
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)

    with app.app_context():
        product = Product.query.filter_by(is_active=True).first()
        prod_id = product.id

    data = {
        'shipping_type': 'delivery',
        'recipient_name': 'Mariana Gómez',
        'phone': '3005551234',
        'city': 'Envigado',
        'neighborhood': 'La Magnolia',
        'street_address': 'Transversal 32 # 35-10',
        'complement': 'Casa 2',
        'fiscal_doc_type': 'NIT',
        'fiscal_doc_number': '900888777-1',
        'fiscal_name': 'Gómez Construcciones SAS',
        'fiscal_email': 'compras@gomezconst.com',
        f'qty_{prod_id}': '1',
        'status': OrderStatus.CONFIRMED,
        'payment_method': PaymentMethod.SIMULATED_TRANSFER,
        'is_paid': '1'
    }

    resp = client.post('/admin/pedidos/nuevo', data=data, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        order = Order.query.filter_by(shipping_recipient_name='Mariana Gómez').first()
        assert order is not None
        assert order.shipping_city == 'Envigado'
        assert order.shipping_cost > 0


def test_admin_search_finds_products_and_orders(app, client):
    """Verifica que la barra de búsqueda del modo admin funciona y busca productos y pedidos."""
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)

    with app.app_context():
        p = Product.query.first()
        sku = p.sku

    # Búsqueda por término general
    resp = client.get(f'/admin/buscar?q={sku[:4]}')
    assert resp.status_code == 200
    assert b"Resultados para:" in resp.data
    assert sku.encode() in resp.data

    # Búsqueda vacía
    resp_empty = client.get('/admin/buscar')
    assert resp_empty.status_code == 200
    assert b"B\xc3\xbasqueda Global del Panel Administrativo" in resp_empty.data or b"Busqueda Global" in resp_empty.data


def test_admin_search_redirects_on_exact_sku_or_order(app, client):
    """Verifica que una búsqueda exacta de SKU o número de orden redirige directamente al detalle."""
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)

    with app.app_context():
        p = Product.query.first()
        sku = p.sku

    resp = client.get(f'/admin/buscar?q={sku}')
    assert resp.status_code == 302
    assert f"/admin/productos/{p.id}/editar" in resp.headers['Location']


def test_admin_search_finds_customers_and_links_to_profile(app, client):
    """Regresión: buscar un cliente no debe dar 500 y debe enlazar a su ficha (user_id)."""
    from app.models.user import User
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)

    with app.app_context():
        customer = User.query.filter_by(email='cliente@correo.com').first()
        cid = customer.id

    resp = client.get('/admin/buscar?q=cliente@correo')
    assert resp.status_code == 200
    assert f'/admin/clientes/{cid}'.encode() in resp.data