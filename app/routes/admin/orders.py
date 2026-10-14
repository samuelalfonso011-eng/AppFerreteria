from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from sqlalchemy import or_
from app.decorators import admin_required
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.forms.admin_forms import OrderStatusForm
from app.services.order_service import OrderService

admin_orders_bp = Blueprint('admin_orders', __name__, url_prefix='/admin/pedidos')


@admin_orders_bp.route('/')
@admin_required
def index():
    """Listado general de pedidos con búsqueda por número o cliente y filtro por estado."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('estado', '').strip()

    query = Order.query.join(User)

    if search:
        query = query.filter(or_(
            Order.order_number.ilike(f"%{search}%"),
            User.full_name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
            Order.shipping_recipient_name.ilike(f"%{search}%")
        ))

    if status_filter in OrderStatus.ALL_STATUSES:
        query = query.filter(Order.status == status_filter)

    pagination = query.order_by(Order.created_at.desc()).paginate(page=page, per_page=15, error_out=False)

    return render_template(
        'admin/orders/list.html',
        pagination=pagination,
        orders=pagination.items,
        current_search=search,
        current_status=status_filter,
        statuses=OrderStatus.ALL_STATUSES,
        labels=OrderStatus.LABELS
    )


@admin_orders_bp.route('/<int:order_id>')
@admin_required
def detail(order_id):
    """Consulta detallada de un pedido con historial de estados y formulario de cambio de estado."""
    order = Order.query.get_or_404(order_id)
    form = OrderStatusForm(new_status=order.status)
    payments = order.payments.order_by(order.payments.property.mapper.class_.created_at.desc()).all()

    return render_template(
        'admin/orders/detail.html',
        order=order,
        form=form,
        payments=payments,
        labels=OrderStatus.LABELS
    )


@admin_orders_bp.route('/<int:order_id>/cambiar-estado', methods=['POST'])
@admin_required
def change_status(order_id):
    """Actualiza el estado del pedido validando la máquina de estados y gestionando inventario."""
    form = OrderStatusForm()
    if form.validate_on_submit():
        new_status = form.new_status.data
        comment = form.comment.data.strip() if form.comment.data else None

        try:
            OrderService.change_order_status(
                order_id=order_id,
                new_status=new_status,
                changed_by_user_id=current_user.id,
                comment=comment
            )
            flash("Estado del pedido actualizado correctamente.", "success")
        except ValueError as e:
            flash(str(e), "danger")

    return redirect(url_for('admin_orders.detail', order_id=order_id))
