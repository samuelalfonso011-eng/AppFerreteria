from sqlalchemy.orm import joinedload
from flask import Blueprint, render_template, request
from sqlalchemy import or_
from app.decorators import admin_required
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.order import Order

admin_payments_bp = Blueprint('admin_payments', __name__, url_prefix='/admin/pagos')


@admin_payments_bp.route('/')
@admin_required
def index():
    """Auditoría y consulta de registros de pagos en modo de prueba."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('estado', '').strip()

    query = Payment.query.options(joinedload(Payment.order).joinedload(Order.user)).join(Order)

    if search:
        query = query.filter(or_(
            Payment.transaction_reference.ilike(f"%{search}%"),
            Order.order_number.ilike(f"%{search}%")
        ))

    if status_filter in PaymentStatus.ALL_STATUSES:
        query = query.filter(Payment.status == status_filter)

    pagination = query.order_by(Payment.created_at.desc()).paginate(page=page, per_page=15, error_out=False)

    return render_template(
        'admin/payments/list.html',
        pagination=pagination,
        payments=pagination.items,
        current_search=search,
        current_status=status_filter,
        statuses=PaymentStatus.ALL_STATUSES,
        labels=PaymentStatus.LABELS
    )
