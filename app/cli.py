import click
from decimal import Decimal
from app.extensions import db
from app.models.user import Role, User
from app.models.category import Category
from app.models.product import Product
from app.models.setting import StoreSetting
from app.models.inventory import InventoryMovement, MovementType


def register_cli_commands(app):
    """Registra comandos seguros en la interfaz de línea de comandos de Flask."""

    @app.cli.command("init-db")
    def init_db():
        """Crea todas las tablas de la base de datos si no existen."""
        db.create_all()
        click.echo(click.style("Tablas de la base de datos creadas/verificadas correctamente.", fg="green"))

    @app.cli.command("expire-orders")
    def expire_orders():
        """Vence los pedidos pendientes sin pago y repone su stock (apto para cron)."""
        from app.services.order_service import OrderService
        n = OrderService.expire_stale_pending_orders()
        click.echo(f"Pedidos vencidos: {n}")

    @app.cli.command("init-roles")
    def init_roles():
        """Crea los roles base del sistema ('admin' y 'customer')."""
        db.create_all()
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrador del sistema y panel de control')
            db.session.add(admin_role)

        customer_role = Role.query.filter_by(name='customer').first()
        if not customer_role:
            customer_role = Role(name='customer', description='Cliente de la tienda virtual')
            db.session.add(customer_role)

        db.session.commit()
        click.echo(click.style("Roles base inicializados correctamente.", fg="green"))

    @app.cli.command("create-admin")
    @click.option("--email", prompt="Correo electrónico del administrador", help="Email del nuevo admin")
    @click.option("--full-name", prompt="Nombre completo", help="Nombre del nuevo admin")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Contraseña segura")
    def create_admin(email, full_name, password):
        """Crea un nuevo usuario administrador de forma segura e interactiva."""
        email_clean = email.strip().lower()

        # Asegurar roles
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrador del sistema')
            db.session.add(admin_role)
            db.session.commit()

        existing = User.query.filter_by(email=email_clean).first()
        if existing:
            click.echo(click.style(f"Error: Ya existe un usuario con el correo '{email_clean}'.", fg="red"))
            return

        admin_user = User(
            email=email_clean,
            full_name=full_name.strip(),
            role_id=admin_role.id,
            is_active=True
        )
        admin_user.set_password(password)
        db.session.add(admin_user)
        db.session.commit()

        click.echo(click.style(f"¡Administrador '{email_clean}' creado exitosamente!", fg="green", bold=True))

    @app.cli.command("seed-demo-data")
    def seed_demo_data():
        """Inicializa categorías y productos de ejemplo de ferretería para desarrollo local."""
        db.create_all()
        # 1. Asegurar roles
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrador del sistema')
            db.session.add(admin_role)

        customer_role = Role.query.filter_by(name='customer').first()
        if not customer_role:
            customer_role = Role(name='customer', description='Cliente de la tienda virtual')
            db.session.add(customer_role)

        db.session.commit()

        # 2. Configuración de tienda
        StoreSetting.get_settings()

        # 3. Categorías de ferretería
        categories_data = [
            ("Herramientas Manuales", "herramientas-manuales", "Martillos, destornilladores, llaves, pinzas y serruchos de alta resistencia."),
            ("Herramientas Eléctricas", "herramientas-electricas", "Taladros, pulidoras, sierras circulares y caladoras para obra."),
            ("Construcción", "construccion", "Cemento, arena, varillas, aditivos y materiales para obra civil."),
            ("Electricidad", "electricidad", "Cables, tomacorrientes, interruptores, canaletas y tableros."),
            ("Pintura y Acabados", "pintura-y-acabados", "Pinturas vinílicas, brochas, rodillos, lijas y solventes."),
            ("Plomería y Tuberías", "plomeria-y-tuberias", "Tubos PVC, accesorios, llaves de paso, pegantes y grifería.")
        ]

        cat_dict = {}
        for name, slug, desc in categories_data:
            cat = Category.query.filter_by(slug=slug).first()
            if not cat:
                cat = Category(name=name, slug=slug, description=desc, is_active=True)
                db.session.add(cat)
                db.session.flush()
            cat_dict[slug] = cat

        # 4. Productos de demostración con inventario real y SKU
        products_data = [
            {
                "category_slug": "herramientas-manuales",
                "sku": "HM-MART-01",
                "name": "Martillo de Uña Curva 16oz Mango Fibra",
                "slug": "martillo-de-una-curva-16oz-mango-fibra",
                "price": Decimal("28500.00"),
                "stock": 25,
                "min_stock_alert": 5,
                "description": "Martillo forjado en acero templado con mango ergonómico de fibra de vidrio anti-vibración.",
                "technical_specs": "Peso cabeza: 16oz (450g) | Material: Acero al carbono | Mango: Fibra de vidrio bimaterial"
            },
            {
                "category_slug": "herramientas-electricas",
                "sku": "HE-TAL-650",
                "name": "Taladro Percutor 1/2 Pulgada 650W",
                "slug": "taladro-percutor-1-2-pulgada-650w",
                "price": Decimal("185000.00"),
                "stock": 12,
                "min_stock_alert": 3,
                "description": "Taladro reversible de velocidad variable con selector de percusión y rotación continua.",
                "technical_specs": "Potencia: 650W | Mandril: 1/2' (13mm) | Velocidad: 0 - 3000 RPM | Impactos: 48000 GPM"
            },
            {
                "category_slug": "electricidad",
                "sku": "EL-CBL-12",
                "name": "Cable Eléctrico THHN Calibre 12 AWG (100m)",
                "slug": "cable-electrico-thhn-calibre-12-awg-100m",
                "price": Decimal("245000.00"),
                "stock": 15,
                "min_stock_alert": 4,
                "description": "Rollo de 100 metros de cable de cobre electrolítico de 99.9% pureza con aislamiento antiflama.",
                "technical_specs": "Calibre: 12 AWG | Longitud: 100m | Aislamiento: PVC 90°C / 600V | Color: Negro"
            },
            {
                "category_slug": "pintura-y-acabados",
                "sku": "PT-VIN-BLANCO",
                "name": "Pintura Vinilo Tipo 1 Blanco Galón",
                "slug": "pintura-vinilo-tipo-1-blanco-galon",
                "price": Decimal("62000.00"),
                "stock": 30,
                "min_stock_alert": 8,
                "description": "Pintura base agua de alta lavabilidad y máximo cubrimiento para interiores y exteriores cubiertos.",
                "technical_specs": "Presentación: Galón (3.785 L) | Acabado: Mate | Rendimiento: 35-40 m² a 2 manos"
            },
            {
                "category_slug": "plomeria-y-tuberias",
                "sku": "PL-PVC-TUB-05",
                "name": "Tubo PVC Presión 1/2 Pulgada RDE 9 (6m)",
                "slug": "tubo-pvc-presion-1-2-pulgada-rde-9-6m",
                "price": Decimal("14500.00"),
                "stock": 50,
                "min_stock_alert": 10,
                "description": "Tubería de PVC para distribución y transporte de agua potable a presión en instalaciones domiciliarias.",
                "technical_specs": "Diámetro: 1/2 pulgada | Longitud: 6 metros | Norma: NTC 382 | RDE: 9"
            },
            {
                "category_slug": "construccion",
                "sku": "CN-CEM-50KG",
                "name": "Cemento Gris de Uso General 50 Kg",
                "slug": "cemento-gris-de-uso-general-50-kg",
                "price": Decimal("32000.00"),
                "stock": 80,
                "min_stock_alert": 20,
                "description": "Cemento hidráulico de alta resistencia inicial y final para pegado de ladrillo, revoques y vigas.",
                "technical_specs": "Peso: 50 Kg | Tipo: Uso general | Fraguado inicial: 90 min"
            }
        ]

        # Encontrar o crear un usuario para auditar el movimiento de inventario inicial
        admin_user = User.query.filter_by(role_id=admin_role.id).first()
        if not admin_user:
            admin_user = User(
                email="sistema@ferreteria.local",
                full_name="Sistema Automático",
                role_id=admin_role.id,
                is_active=True
            )
            admin_user.set_password("system_seed_password_protected_2026")
            db.session.add(admin_user)
            db.session.flush()

        for p_data in products_data:
            cat = cat_dict.get(p_data["category_slug"])
            prod = Product.query.filter_by(sku=p_data["sku"]).first()
            if not prod:
                prod = Product(
                    category_id=cat.id,
                    sku=p_data["sku"],
                    name=p_data["name"],
                    slug=p_data["slug"],
                    price=p_data["price"],
                    stock=p_data["stock"],
                    min_stock_alert=p_data["min_stock_alert"],
                    description=p_data["description"],
                    technical_specs=p_data["technical_specs"],
                    is_active=True
                )
                db.session.add(prod)
                db.session.flush()

                # Registrar movimiento inicial de inventario en el kárdex
                movement = InventoryMovement(
                    product_id=prod.id,
                    user_id=admin_user.id,
                    movement_type=MovementType.PURCHASE_ENTRY,
                    quantity=prod.stock,
                    previous_stock=0,
                    new_stock=prod.stock,
                    reason="Inventario inicial por siembra de catálogo",
                    reference_id="SEED-INIT"
                )
                db.session.add(movement)

        db.session.commit()
        click.echo(click.style("Catálogo de ferretería y datos demo sembrados con éxito.", fg="green", bold=True))
