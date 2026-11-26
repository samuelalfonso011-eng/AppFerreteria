"""Comandos: flask --app run init-db | seed-demo | create-admin"""
from decimal import Decimal

import click

from app.extensions import db


def _password_problem(password, email=None):
    # Misma regla que el registro web
    from app.services.auth_service import password_problem
    return password_problem(password, email)


DEMO_CATEGORIES = [
    # nombre, titular de portada, arte, orden
    ("Eléctricas", None, "drill", 1),
    ("Manuales", "Kit Herramientas Manuales", "wrench", 2),
    ("Pinturas", "Pinturas y Acabados", "roller", 3),
    ("Iluminación", "Iluminación LED Smart", "lamp", 4),
    ("Seguridad", "Seguridad Industrial", "helmet", 5),
]

DEMO_PRODUCTS = [
    # sku, nombre, slug, categoria, precio, arte, stock, descripcion, especificaciones
    ("FP-0001", "Taladro Percutor Pro X1", "taladro-percutor-pro-x1", "Eléctricas", 489900, "drill", 18,
     "Motor sin escobillas y batería de 20 V para perforar y atornillar.",
     "Motor sin escobillas\nBatería de 20 V y 4 Ah\nMandril de 13 mm\nDos velocidades y función percutor"),
    ("FP-0002", "Sierra Circular M4", "sierra-circular-m4", "Eléctricas", 369900, "saw", 9,
     "Base metálica y empuñadura doble para guiar cortes rectos en madera.",
     "Disco de 185 mm\nProfundidad de corte de 65 mm\nBase de aluminio con bisel de 0 a 45 grados"),
    ("FP-0003", "Kit de llaves combinadas", "kit-de-llaves-combinadas", "Manuales", 89900, "wrench", 30,
     "Llaves de acero con boca abierta y extremo de estrella.",
     "12 piezas de 8 a 19 mm\nAcero cromo vanadio\nEstuche enrollable"),
    ("FP-0004", "Rodillo de microfibra", "rodillo-de-microfibra", "Pinturas", 24900, "roller", 45,
     "Rodillo de pelo corto para aplicar acabados uniformes en superficies lisas.",
     "Ancho de 23 cm\nPelo corto de 9 mm\nMango ergonómico con rosca para extensión"),
    ("FP-0005", "Bombilla LED Smart", "bombilla-led-smart", "Iluminación", 54900, "lamp", 4,
     "Luz regulable para adaptar la iluminación del espacio de trabajo.",
     "10 W equivalentes a 75 W\nRosca E27\nTemperatura regulable de 2700 K a 6500 K"),
    ("FP-0006", "Casco de seguridad", "casco-de-seguridad", "Seguridad", 39900, "helmet", 25,
     "Casco de obra con ajuste de contorno y visera frontal.",
     "Polietileno de alta densidad\nAjuste de rache\nUso industrial clase E"),
]


def ensure_base_rows():
    from app import models  # noqa: F401  (registra todas las tablas)
    from app.models import StoreSetting
    from app.utils.cache import ensure_cache_rows
    if db.engine.dialect.name == "sqlite":
        db.create_all()
    ensure_cache_rows()
    if StoreSetting.query.first() is None:
        db.session.add(StoreSetting())
    db.session.commit()


def seed_demo_data():
    """Idempotente: solo crea lo que falta."""
    from app.models import Category, MovementType, Product
    from app.services import inventory_service

    ensure_base_rows()
    categories = {}
    for name, headline, art, order in DEMO_CATEGORIES:
        category = Category.query.filter_by(name=name).first()
        if category is None:
            from app.utils.validation import slugify
            category = Category(name=name, slug=slugify(name, 100), headline=headline, art=art, sort_order=order)
            db.session.add(category)
        categories[name] = category
    db.session.flush()

    created = 0
    for sku, name, slug, cat, price, art, stock, desc, specs in DEMO_PRODUCTS:
        if Product.query.filter_by(sku=sku).first():
            continue
        product = Product(sku=sku, name=name, slug=slug, category=categories[cat], price=Decimal(price),
                          stock=0, min_stock_alert=5, art=art, description=desc, specs=specs)
        db.session.add(product)
        db.session.flush()
        inventory_service.increase(product, stock, MovementType.PURCHASE_ENTRY, "Inventario inicial de demostración")
        created += 1
    db.session.commit()
    return created


def register_cli(app):
    @app.cli.command("verify-integrity")
    def verify_integrity():
        """Audita la cadena como sistema. Sale con código 1 si encuentra una divergencia."""
        import json
        from app.services.integrity_service import verify_chain

        report = verify_chain()
        click.echo(json.dumps(report.to_dict(), ensure_ascii=False))
        if report.status == "compromised":
            raise click.exceptions.Exit(1)

    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas y las filas base (ajustes y tokens de cache)."""
        ensure_base_rows()
        click.echo("Base de datos lista.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Carga las categorias y productos de la tienda de la Fase 1."""
        created = seed_demo_data()
        click.echo(f"Datos de demostración cargados: {created} productos nuevos.")

    @app.cli.command("create-admin")
    @click.option("--email", prompt="Correo del administrador")
    @click.option("--name", prompt="Nombre completo")
    @click.option("--reset", is_flag=True, help="Si el correo existe, lo convierte en admin y cambia la contraseña.")
    def create_admin(email, name, reset):
        """Crea una cuenta administradora. La contraseña se pide sin mostrarla y se guarda con hash."""
        from app.models import User
        from app.utils.validation import EMAIL_RE
        ensure_base_rows()
        email = email.strip().lower()
        if not EMAIL_RE.fullmatch(email):
            raise click.ClickException("Correo no válido.")
        name = " ".join(name.split())
        if len(name) < 3:
            raise click.ClickException("Escribe el nombre completo.")
        user = User.by_email(email)
        if user is not None and not reset:
            raise click.ClickException("Ese correo ya existe. Usa --reset para cambiar su contraseña y rol.")
        password = click.prompt("Contraseña", hide_input=True, confirmation_prompt="Repite la contraseña")
        problem = _password_problem(password, email)
        if problem:
            raise click.ClickException(problem)
        if user is None:
            user = User(email=email, full_name=name, role=User.ROLE_ADMIN)
            db.session.add(user)
        user.full_name = name
        user.role = User.ROLE_ADMIN
        user.is_active = True
        user.email_verification_pending = False
        user.set_password(password)
        db.session.commit()
        click.echo(f"Administrador listo: {email}")
