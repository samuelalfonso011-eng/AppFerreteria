from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from sqlalchemy import or_
from app.decorators import admin_required
from app.extensions import db
from app.models.product import Product
from app.models.category import Category
from app.models.category import generate_unique_slug
from app.models.inventory import InventoryMovement, MovementType
from app.models.order import OrderItem
from app.forms.product_forms import ProductForm
from app.services.image_service import ImageService

admin_products_bp = Blueprint('admin_products', __name__, url_prefix='/admin/productos')


@admin_products_bp.route('/')
@admin_required
def index():
    """Listado de productos para gestión administrativa."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    cat_id = request.args.get('categoria', type=int)
    status_filter = request.args.get('estado', '').strip()

    query = Product.query

    if search:
        query = query.filter(or_(
            Product.name.ilike(f"%{search}%"),
            Product.sku.ilike(f"%{search}%")
        ))
    if cat_id:
        query = query.filter_by(category_id=cat_id)
    if status_filter == 'activo':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactivo':
        query = query.filter_by(is_active=False)

    pagination = query.order_by(Product.name.asc()).paginate(page=page, per_page=15, error_out=False)
    categories = Category.query.order_by(Category.name).all()

    return render_template(
        'admin/products/list.html',
        pagination=pagination,
        products=pagination.items,
        categories=categories,
        current_search=search,
        current_cat=cat_id,
        current_status=status_filter
    )


@admin_products_bp.route('/crear', methods=['GET', 'POST'])
@admin_required
def create():
    """Creación de un nuevo producto con validación de imagen y kárdex inicial."""
    form = ProductForm()
    if form.validate_on_submit():
        sku_clean = form.sku.data.strip().upper()
        slug_base = generate_unique_slug(form.name.data, Product)

        # Manejo de imagen local
        image_filename = None
        if form.image.data:
            try:
                image_filename = ImageService.save_product_image(form.image.data)
            except ValueError as e:
                flash(f"Error en la imagen: {str(e)}", "danger")
                return render_template('admin/products/form.html', form=form, title="Crear Producto")

        product = Product(
            category_id=form.category_id.data,
            sku=sku_clean,
            name=form.name.data.strip(),
            slug=slug_base,
            description=form.description.data.strip(),
            technical_specs=form.technical_specs.data.strip() if form.technical_specs.data else None,
            price=form.price.data,
            stock=form.stock.data,
            min_stock_alert=form.min_stock_alert.data,
            image_path=image_filename,
            is_active=form.is_active.data
        )
        db.session.add(product)
        db.session.flush()

        # Auditoría de inventario inicial si se crea con stock
        if product.stock > 0:
            movement = InventoryMovement(
                product_id=product.id,
                user_id=current_user.id,
                movement_type=MovementType.PURCHASE_ENTRY,
                quantity=product.stock,
                previous_stock=0,
                new_stock=product.stock,
                reason="Stock inicial por creación de producto",
                reference_id="PRODUCT-CREATE"
            )
            db.session.add(movement)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if image_filename:
                ImageService.delete_product_image(image_filename)  # evita imágenes huérfanas
            raise
        flash(f"Producto '{product.name}' registrado exitosamente con SKU: {product.sku}.", "success")
        return redirect(url_for('admin_products.index'))

    return render_template('admin/products/form.html', form=form, title="Crear Producto")


@admin_products_bp.route('/<int:product_id>/editar', methods=['GET', 'POST'])
@admin_required
def edit(product_id):
    """Edición de datos de un producto."""
    product = db.get_or_404(Product, product_id)
    form = ProductForm(original_sku=product.sku, obj=product)

    if form.validate_on_submit():
        product.name = form.name.data.strip()
        product.category_id = form.category_id.data
        product.sku = form.sku.data.strip().upper()
        product.description = form.description.data.strip()
        product.technical_specs = form.technical_specs.data.strip() if form.technical_specs.data else None
        product.price = form.price.data
        product.min_stock_alert = form.min_stock_alert.data
        product.is_active = form.is_active.data

        # Actualizar imagen si se subió una nueva
        old_img = None
        new_img = None
        if form.image.data:
            try:
                new_img = ImageService.save_product_image(form.image.data)
                old_img = product.image_path
                product.image_path = new_img
            except ValueError as e:
                flash(f"Error en la imagen: {str(e)}", "danger")
                return render_template('admin/products/form.html', form=form, product=product, title="Editar Producto")

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if new_img:
                ImageService.delete_product_image(new_img)
            raise
        # La imagen anterior solo se borra cuando el cambio ya quedó guardado
        if old_img:
            ImageService.delete_product_image(old_img)
        flash("Producto actualizado correctamente.", "success")
        return redirect(url_for('admin_products.index'))

    return render_template('admin/products/form.html', form=form, product=product, title="Editar Producto")


@admin_products_bp.route('/<int:product_id>/alternar-estado', methods=['POST'])
@admin_required
def toggle_status(product_id):
    """Activa o desactiva un producto del catálogo comercial."""
    product = db.get_or_404(Product, product_id)
    product.is_active = not product.is_active
    db.session.commit()
    estado_str = "activado" if product.is_active else "desactivado"
    flash(f"El producto '{product.name}' ha sido {estado_str}.", "info")
    return redirect(url_for('admin_products.index'))


@admin_products_bp.route('/<int:product_id>/eliminar', methods=['POST'])
@admin_required
def delete(product_id):
    """
    Eliminación segura:
    Verifica integridad referencial. Si el producto tiene pedidos asociados,
    impide el borrado físico para conservar el historial comercial y recomienda desactivar.
    """
    product = db.get_or_404(Product, product_id)

    # Verificar si tiene líneas de pedido históricas
    has_orders = OrderItem.query.filter_by(product_id=product.id).first() is not None
    if has_orders:
        flash("No es posible eliminar este producto porque ya forma parte del historial de ventas. En su lugar, desactívalo.", "warning")
        return redirect(url_for('admin_products.index'))

    # Borrar imagen física si no está referenciada
    if product.image_path:
        ImageService.delete_product_image(product.image_path)

    db.session.delete(product)
    db.session.commit()
    flash(f"El producto '{product.name}' fue eliminado exitosamente.", "info")
    return redirect(url_for('admin_products.index'))
