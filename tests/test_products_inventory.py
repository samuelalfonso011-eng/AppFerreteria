import pytest
from decimal import Decimal
import io
from app.models.product import Product
from app.models.inventory import InventoryMovement, MovementType
from app.services.inventory_service import InventoryService
from app.services.image_service import ImageService


def login_admin(client):
    client.post('/login', data={
        'email': 'admin@ferreteria.com',
        'password': 'AdminPass123*'
    }, follow_redirects=True)


def test_9_admin_can_create_product(client, app):
    """Criterio 9: Un administrador puede crear productos."""
    login_admin(client)

    response = client.post('/admin/productos/crear', data={
        'name': 'Destornillador de Pala',
        'category_id': 1,
        'sku': 'HM-DEST-01',
        'description': 'Destornillador con punta magnética',
        'price': '8500.00',
        'stock': '20',
        'min_stock_alert': '5',
        'is_active': True
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        p = Product.query.filter_by(sku='HM-DEST-01').first()
        assert p is not None
        assert p.name == 'Destornillador de Pala'
        assert p.stock == 20


def test_10_admin_can_edit_product(client, app):
    """Criterio 10: Un administrador puede editar productos."""
    login_admin(client)

    response = client.post('/admin/productos/1/editar', data={
        'name': 'Martillo de Prueba Modificado',
        'category_id': 1,
        'sku': 'HM-MART-TEST',
        'description': 'Descripción actualizada',
        'price': '29900.00',
        'min_stock_alert': '4',
        'is_active': True
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        p = Product.query.get(1)
        assert p.name == 'Martillo de Prueba Modificado'
        assert p.price == Decimal('29900.00')


def test_11_and_12_deactivated_product_cannot_be_bought(client, app):
    """Criterio 11 y 12: Un administrador puede desactivar productos y no pueden comprarse."""
    login_admin(client)

    # Desactivar producto
    client.post('/admin/productos/1/alternar-estado', follow_redirects=True)

    with app.app_context():
        p = Product.query.get(1)
        assert not p.is_active

    # Intentar agregarlo al carrito debe fallar
    cart_res = client.post('/carrito/agregar', data={
        'product_id': 1,
        'quantity': 1
    }, follow_redirects=True)
    assert "El producto no existe o está desactivado".encode('utf-8') in cart_res.data


def test_13_negative_prices_are_rejected(client):
    """Criterio 13: Los precios negativos son rechazados."""
    login_admin(client)

    response = client.post('/admin/productos/crear', data={
        'name': 'Producto Precio Negativo',
        'category_id': 1,
        'sku': 'HM-BAD-01',
        'description': 'Test',
        'price': '-500.00',
        'stock': '10',
        'min_stock_alert': '2',
        'is_active': True
    })
    assert "El precio no puede ser negativo".encode('utf-8') in response.data


def test_14_invalid_images_are_rejected():
    """Criterio 14: Los archivos no válidos (que no sean imágenes reales) son rechazados."""
    fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00This is a fake executable")
    fake_exe.filename = "malicious.exe"

    with pytest.raises(ValueError) as exc:
        ImageService.save_product_image(fake_exe)
    assert "Formato no permitido" in str(exc.value) or "imagen válida" in str(exc.value)


def test_15_and_16_inventory_movements_and_non_negative_stock(app):
    """Criterio 15 y 16: El inventario no puede ser negativo y los movimientos quedan registrados."""
    with app.app_context():
        # Ajuste manual a 15
        mov = InventoryService.adjust_stock(
            product_id=1,
            user_id=1,
            target_stock=15,
            reason="Ajuste positivo de prueba"
        )
        assert mov.movement_type == MovementType.ADJUSTMENT_IN
        assert mov.new_stock == 15
        assert mov.quantity == 5

        # Intento de ajuste a valor negativo debe lanzar ValueError
        with pytest.raises(ValueError):
            InventoryService.adjust_stock(product_id=1, user_id=1, target_stock=-5, reason="Negativo")
