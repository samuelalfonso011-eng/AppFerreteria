from flask import Blueprint, render_template, request
from app.models.category import Category
from app.models.product import Product
from app.models.setting import StoreSetting

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def home():
    """Página principal de la ferretería con categorías, destacados y ofertas."""
    settings = StoreSetting.get_settings()
    
    # Categorías activas
    categories = Category.query.filter_by(is_active=True).all()
    
    # Productos destacados (activos y con inventario)
    featured_products = Product.query.filter_by(is_active=True).filter(Product.stock > 0).limit(8).all()
    
    # Novedades (productos añadidos recientemente)
    recent_products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(4).all()

    return render_template(
        'home.html',
        settings=settings,
        categories=categories,
        featured_products=featured_products,
        recent_products=recent_products
    )


@public_bp.route('/nosotros')
def about():
    """Página institucional de la ferretería."""
    settings = StoreSetting.get_settings()
    return render_template('about.html', settings=settings)


@public_bp.route('/contacto')
def contact():
    """Página de contacto y ubicación física."""
    settings = StoreSetting.get_settings()
    return render_template('contact.html', settings=settings)


@public_bp.route('/entregas')
def delivery_info():
    """Información sobre políticas de entregas a domicilio y tarifas."""
    settings = StoreSetting.get_settings()
    return render_template('delivery_info.html', settings=settings)
