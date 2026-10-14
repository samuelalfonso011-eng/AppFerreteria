from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models.order import Order
from app.services.order_service import OrderService

orders_bp = Blueprint('orders', __name__, url_prefix='/mis-pedidos')


@orders_bp.route('/')
@login_required
def my_orders():
    """Consulta de historial de pedidos exclusivos del cliente autenticado."""
    page = request.args.get('page', 1, type=int)
    pagination = Order.query.filter_by(user_id=current_user.id)\
        .order_by(Order.created_at.desc())\
        .paginate(page=page, per_page=10, error_out=False)

    return render_template(
        'orders/my_orders.html',
        pagination=pagination,
        orders=pagination.items
    )


@orders_bp.route('/<order_number>')
@login_required
def detail(order_number):
    """Consulta detallada de un pedido personal con precios históricos y trazabilidad."""
    # Control de acceso estricto: el cliente solo puede consultar sus propios pedidos
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    latest_payment = order.payments.order_by(order.payments.property.mapper.class_.created_at.desc()).first()

    return render_template(
        'orders/order_detail.html',
        order=order,
        latest_payment=latest_payment
    )


@orders_bp.route('/<order_number>/cancelar', methods=['POST'])
@login_required
def cancel(order_number):
    """Permite al cliente cancelar su propio pedido si las reglas de negocio lo permiten."""
    reason = request.form.get('reason', '').strip()

    try:
        order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
        OrderService.cancel_by_customer(
            order_id=order.id,
            customer_user_id=current_user.id,
            reason=reason
        )
        flash(f"El pedido #{order_number} ha sido cancelado y las unidades han sido repuestas al inventario.", "info")
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for('orders.detail', order_number=order_number))
