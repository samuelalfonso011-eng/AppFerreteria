from decimal import Decimal
from flask import Blueprint, render_template, request, abort
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from app.models.category import Category
from app.models.product import Product

products_bp = Blueprint('products', __name__, url_prefix='/productos')


@products_bp.route('/')
def catalog():
    """Catálogo de productos con búsqueda, filtros múltiples, ordenamiento y paginación."""
    page = request.args.get('page', 1, type=int)
    per_page = 12

    # Parámetros de búsqueda y filtros
    query = (request.args.get('q') or request.args.get('search') or '').strip()
    category_slug = request.args.get('categoria', '').strip()
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    availability = request.args.get('disponibilidad', '').strip()
    sort_by = request.args.get('orden', 'nuevos').strip()

    # Base query: Solo productos activos con joinedload para evitar N+1
    products_query = Product.query.options(joinedload(Product.category)).filter_by(is_active=True)

    # 1. Búsqueda por término (nombre, SKU o descripción)
    if query:
        search_filter = or_(
            Product.name.ilike(f"%{query}%"),
            Product.sku.ilike(f"%{query}%"),
            Product.description.ilike(f"%{query}%")
        )
        products_query = products_query.filter(search_filter)

    # 2. Filtro por categoría
    selected_category = None
    if category_slug:
        selected_category = Category.query.filter_by(slug=category_slug, is_active=True).first()
        if selected_category:
            products_query = products_query.filter_by(category_id=selected_category.id)

    # 3. Filtro por rango de precio
    if min_price is not None and min_price >= 0:
        products_query = products_query.filter(Product.price >= Decimal(str(min_price)))
    if max_price is not None and max_price >= 0:
        products_query = products_query.filter(Product.price <= Decimal(str(max_price)))

    # 4. Filtro por disponibilidad
    if availability == 'in_stock':
        products_query = products_query.filter(Product.stock > 0)
    elif availability == 'out_of_stock':
        products_query = products_query.filter(Product.stock == 0)

    # 5. Ordenamiento
    if sort_by == 'precio_asc':
        products_query = products_query.order_by(Product.price.asc())
    elif sort_by == 'precio_desc':
        products_query = products_query.order_by(Product.price.desc())
    elif sort_by == 'nombre':
        products_query = products_query.order_by(Product.name.asc())
    else:  # 'nuevos' por defecto
        products_query = products_query.order_by(Product.created_at.desc())

    # Paginación segura
    pagination = products_query.paginate(page=page, per_page=per_page, error_out=False)
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()

    return render_template(
        'products/catalog.html',
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        selected_category=selected_category,
        current_query=query,
        current_category=category_slug,
        current_min_price=min_price,
        current_max_price=max_price,
        current_availability=availability,
        current_sort=sort_by
    )


@products_bp.route('/<slug>')
def detail(slug):
    """Ficha detallada del producto con especificaciones y disponibilidad real."""
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    
    # Productos relacionados de la misma categoría
    related_products = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.is_active == True
    ).limit(4).all()

    return render_template(
        'products/detail.html',
        product=product,
        related_products=related_products
    )
