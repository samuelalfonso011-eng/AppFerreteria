"""
Pruebas automatizadas para las correcciones de backend v1.2.0:
- Consulta de detalle de pedido en /admin/pedidos/<id> sin AttributeError.
- Confirmación de orden y latest_payment sin AttributeError.
- Funcionamiento de búsqueda con usuario anónimo, cliente y admin.
- Formateo de fechas en zona horaria America/Bogota (UTC-5).
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.utils.timezone import to_bogota, format_bogota


def test_order_detail_and_confirmation_no_attribute_error(client, app):
    """Verifica que /admin/pedidos/<id> y /mis-pedidos/<order_number> no lancen AttributeError."""
    with app.app_context():
        # Crear un pedido con un pago de prueba
        order = Order(
            order_number="ORD-TEST-120",
            user_id=2,  # cliente
            status=OrderStatus.CONFIRMED,
            subtotal=Decimal("25000.00"),
            shipping_cost=Decimal("10000.00"),
            total=Decimal("35000.00"),
            shipping_recipient_name="Juan Perez",
            shipping_phone="300 000 0000",
            shipping_department="Antioquia",
            shipping_city="Medellín",
            shipping_neighborhood="El Poblado",
            shipping_street_address="Calle 10 # 40-20"
        )
        from app.extensions import db
        db.session.add(order)
        db.session.flush()

        payment = Payment(
            order_id=order.id,
            transaction_reference="TX-TEST-120",
            payment_method=PaymentMethod.SIMULATED_CARD,
            amount=Decimal("35000.00"),
            status=PaymentStatus.APPROVED
        )
        db.session.add(payment)
        db.session.commit()
        order_id = order.id
        order_number = order.order_number

    # 1. Probar acceso admin a /admin/pedidos/<id>
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)
    res_admin = client.get(f'/admin/pedidos/{order_id}')
    assert res_admin.status_code == 200
    assert b"ORD-TEST-120" in res_admin.data
    assert b"Aprobado" in res_admin.data

    # 2. Probar acceso cliente a /mis-pedidos/<order_number>
    client.post('/logout')
    client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}, follow_redirects=True)
    res_client = client.get(f'/mis-pedidos/{order_number}')
    assert res_client.status_code == 200
    assert b"ORD-TEST-120" in res_client.data

    # 3. Probar confirmación de checkout
    res_conf = client.get(f'/checkout/confirmacion/{order_number}')
    assert res_conf.status_code == 200


def test_search_catalog_with_all_sessions(client):
    """Verifica que el catálogo responda con éxito a búsquedas para anónimo, cliente y admin."""
    # Anónimo
    res_anon = client.get('/productos/?q=martillo')
    assert res_anon.status_code == 200

    # Cliente
    client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}, follow_redirects=True)
    res_client = client.get('/productos/?q=martillo')
    assert res_client.status_code == 200

    # Soporte para parámetro search
    res_search = client.get('/productos/?search=martillo')
    assert res_search.status_code == 200

    # Admin
    client.post('/logout')
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)
    res_admin = client.get('/productos/?q=martillo')
    assert res_admin.status_code == 200


def test_bogota_timezone_conversion():
    """Verifica que 03:34 AM UTC corresponda a 10:34 PM UTC-5 del día anterior."""
    utc_dt = datetime(2026, 10, 13, 3, 34, 0, tzinfo=timezone.utc)
    bogota_dt = to_bogota(utc_dt)
    assert bogota_dt.hour == 22  # 10 PM
    assert bogota_dt.day == 12   # Día anterior
    formatted = format_bogota(utc_dt)
    assert "10:34 p. m." in formatted
    assert "12/10/2026" in formatted
