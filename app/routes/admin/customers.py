from flask import Blueprint, render_template, redirect, url_for, flash, request
from sqlalchemy import or_, func
from app.decorators import admin_required
from app.extensions import db
from app.models.user import User, Role
from app.models.order import Order

admin_customers_bp = Blueprint('admin_customers', __name__, url_prefix='/admin/clientes')


@admin_customers_bp.route('/')
@admin_required
def index():
    """Listado de clientes registrados con métricas de compras."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()

    customer_role = Role.query.filter_by(name='customer').first()
    query = User.query.filter_by(role_id=customer_role.id if customer_role else 0)

    if search:
        query = query.filter(or_(
            User.full_name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
            User.phone.ilike(f"%{search}%")
        ))

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=15, error_out=False)

    return render_template(
        'admin/customers/list.html',
        pagination=pagination,
        customers=pagination.items,
        current_search=search
    )


@admin_customers_bp.route('/<int:user_id>')
@admin_required
def detail(user_id):
    """Consulta de información de un cliente e historial de sus pedidos."""
    customer = db.get_or_404(User, user_id)
    orders = customer.orders.order_by(Order.created_at.desc()).all()

    total_spent = sum((o.total for o in orders if o.status not in ['CANCELLED', 'PENDING_CONFIRMATION']), 0)

    return render_template(
        'admin/customers/detail.html',
        customer=customer,
        orders=orders,
        total_spent=total_spent
    )


@admin_customers_bp.route('/<int:user_id>/alternar-estado', methods=['POST'])
@admin_required
def toggle_status(user_id):
    """Desactiva o reactiva el acceso de un cliente al sistema."""
    customer = db.get_or_404(User, user_id)
    customer.is_active = not customer.is_active
    db.session.commit()
    estado_str = "reactivada" if customer.is_active else "desactivada"
    flash(f"La cuenta de '{customer.email}' ha sido {estado_str}.", "info")
    return redirect(url_for('admin_customers.detail', user_id=customer.id))
