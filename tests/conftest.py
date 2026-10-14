import pytest
from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models.user import Role, User, Address
from app.models.category import Category
from app.models.product import Product
from app.models.setting import StoreSetting
from app.models.inventory import InventoryMovement, MovementType


@pytest.fixture
def app():
    """Crea la aplicación Flask en entorno de pruebas con base de datos en memoria."""
    app = create_app('testing')

    with app.app_context():
        db.create_all()

        # Sembrar roles
        admin_role = Role(name='admin', description='Administrador')
        customer_role = Role(name='customer', description='Cliente')
        db.session.add_all([admin_role, customer_role])
        db.session.flush()

        # Sembrar configuración de tienda
        setting = StoreSetting(
            store_name="Ferretería El Constructor",
            phone="300 000 0000",
            email="contacto@ferreteria.com",
            address="Calle 50 # 45-20, Medellín",
            business_hours="L-V: 8-6",
            default_shipping_cost=Decimal("10000.00"),
            free_shipping_threshold=Decimal("200000.00")
        )
        db.session.add(setting)

        # Sembrar usuario admin de prueba
        admin_user = User(
            email="admin@ferreteria.com",
            full_name="Administrador General",
            role=admin_role,
            is_active=True
        )
        admin_user.set_password("AdminPass123*")

        # Sembrar cliente de prueba
        customer_user = User(
            email="cliente@correo.com",
            full_name="Juan Perez",
            role=customer_role,
            is_active=True
        )
        customer_user.set_password("ClientePass123*")

        # Sembrar categoría y producto de prueba
        cat = Category(name="Herramientas", slug="herramientas", is_active=True)
        db.session.add_all([admin_user, customer_user, cat])
        db.session.flush()

        prod = Product(
            category_id=cat.id,
            sku="HM-MART-TEST",
            name="Martillo de Prueba",
            slug="martillo-de-prueba",
            price=Decimal("25000.00"),
            stock=10,
            min_stock_alert=3,
            description="Martillo de prueba para suite automatizada",
            is_active=True
        )
        db.session.add(prod)
        db.session.flush()

        # Movimiento de inventario inicial
        mov = InventoryMovement(
            product_id=prod.id,
            user_id=admin_user.id,
            movement_type=MovementType.PURCHASE_ENTRY,
            quantity=10,
            previous_stock=0,
            new_stock=10,
            reason="Inventario inicial de prueba"
        )
        db.session.add(mov)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Cliente de pruebas HTTP de Flask."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Ejecutor de comandos CLI de Flask."""
    return app.test_cli_runner()
