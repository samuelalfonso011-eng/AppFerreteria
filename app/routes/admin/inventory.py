from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from app.decorators import admin_required
from app.extensions import db
from app.models.inventory import InventoryMovement, MovementType
from app.models.product import Product
from app.forms.admin_forms import StockAdjustmentForm
from app.services.inventory_service import InventoryService

admin_inventory_bp = Blueprint('admin_inventory', __name__, url_prefix='/admin/inventario')


@admin_inventory_bp.route('/')
@admin_required
def index():
    """Kárdex general de movimientos de inventario con filtros y auditoría."""
    page = request.args.get('page', 1, type=int)
    prod_id = request.args.get('producto_id', type=int)
    m_type = request.args.get('tipo', '').strip()

    query = InventoryMovement.query

    if prod_id:
        query = query.filter_by(product_id=prod_id)
    if m_type:
        query = query.filter_by(movement_type=m_type)

    pagination = query.order_by(InventoryMovement.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    products = Product.query.order_by(Product.name).all()

    return render_template(
        'admin/inventory/kardex.html',
        pagination=pagination,
        movements=pagination.items,
        products=products,
        current_prod_id=prod_id,
        current_type=m_type,
        movement_types=MovementType.ALL_TYPES
    )


@admin_inventory_bp.route('/alertas')
@admin_required
def alerts():
    """Consulta de productos con existencias bajas o totalmente agotados."""
    out_of_stock = Product.query.filter_by(is_active=True, stock=0).order_by(Product.name).all()
    low_stock = Product.query.filter(
        Product.is_active == True,
        Product.stock > 0,
        Product.stock <= Product.min_stock_alert
    ).order_by(Product.stock.asc()).all()

    return render_template(
        'admin/inventory/alerts.html',
        out_of_stock=out_of_stock,
        low_stock=low_stock
    )


@admin_inventory_bp.route('/ajuste/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def adjust(product_id):
    """Ajuste manual de existencias con justificación y registro en kárdex."""
    product = db.get_or_404(Product, product_id)
    form = StockAdjustmentForm(target_stock=product.stock)

    if form.validate_on_submit():
        try:
            InventoryService.adjust_stock(
                product_id=product.id,
                user_id=current_user.id,
                target_stock=form.target_stock.data,
                reason=form.reason.data.strip()
            )
            flash(f"Ajuste registrado en el Kárdex para '{product.name}'. Nuevo stock: {form.target_stock.data} unidades.", "success")
            return redirect(url_for('admin_inventory.index', producto_id=product.id))
        except ValueError as e:
            flash(str(e), "danger")

    return render_template('admin/inventory/adjust.html', form=form, product=product)
