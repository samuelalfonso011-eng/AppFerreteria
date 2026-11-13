from sqlalchemy.orm import joinedload
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user
from sqlalchemy import or_
from app.decorators import admin_required
from app.extensions import db
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

    query = Order.query.options(joinedload(Order.user)).join(User)

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
    order = db.get_or_404(Order, order_id)
    form = OrderStatusForm(new_status=order.status)
    payments = order.all_payments

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


@admin_orders_bp.route('/nuevo', methods=['GET', 'POST'])
@admin_required
def create():
    """Generación manual de nuevos pedidos directamente desde el panel de administración."""
    from app.models.product import Product
    from app.models.payment import PaymentMethod
    from app.models.setting import StoreSetting
    from app.constants import VALLE_DE_ABURRA_MUNICIPALITIES

    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
    customers = User.query.filter(User.role.has(name='customer')).order_by(User.full_name.asc()).all()
    settings = StoreSetting.get_settings()

    if request.method == 'POST':
        customer_user_id = request.form.get('customer_user_id')
        customer_user = None
        if customer_user_id and customer_user_id.isdigit():
            customer_user = db.session.get(User, int(customer_user_id))

        recipient_name = request.form.get('recipient_name', '').strip()
        if not recipient_name and customer_user:
            recipient_name = customer_user.full_name

        phone = request.form.get('phone', '').strip()
        if not phone and customer_user:
            phone = customer_user.phone or ''

        shipping_type = request.form.get('shipping_type', 'delivery')
        if shipping_type == 'pickup':
            shipping_data = {
                'shipping_type': 'pickup',
                'recipient_name': recipient_name or 'Cliente de Mostrador',
                'phone': phone or '0000000',
                'department': 'Antioquia',
                'city': 'Medellín',
                'neighborhood': 'Centro (Mostrador)',
                'street_address': 'Retiro en Tienda / Mostrador Principal',
                'complement': 'Entrega inmediata en caja',
                'delivery_instructions': request.form.get('delivery_instructions', '').strip()
            }
        else:
            city = request.form.get('city', 'Medellín').strip()
            shipping_data = {
                'shipping_type': 'delivery',
                'recipient_name': recipient_name,
                'phone': phone,
                'department': 'Antioquia',
                'city': city,
                'neighborhood': request.form.get('neighborhood', '').strip(),
                'street_address': request.form.get('street_address', '').strip(),
                'complement': request.form.get('complement', '').strip(),
                'delivery_instructions': request.form.get('delivery_instructions', '').strip()
            }
            if not shipping_data['recipient_name'] or not shipping_data['street_address'] or not shipping_data['phone']:
                flash("Para despacho a domicilio, el nombre, teléfono y dirección exacta son obligatorios.", "danger")
                return render_template(
                    'admin/orders/create.html',
                    products=products,
                    customers=customers,
                    municipalities=VALLE_DE_ABURRA_MUNICIPALITIES,
                    settings=settings,
                    statuses=OrderStatus.ALL_STATUSES,
                    status_labels=OrderStatus.LABELS,
                    payment_methods=PaymentMethod.ALL_METHODS,
                    payment_labels=PaymentMethod.LABELS
                )

        items_data = []
        for p in products:
            qty_str = request.form.get(f'qty_{p.id}', '0').strip()
            if qty_str and qty_str.isdigit():
                qty = int(qty_str)
                if qty > 0:
                    items_data.append({'product_id': p.id, 'quantity': qty})

        if not items_data:
            flash("Debes seleccionar al menos un producto con cantidad mayor a cero.", "warning")
            return render_template(
                'admin/orders/create.html',
                products=products,
                customers=customers,
                municipalities=VALLE_DE_ABURRA_MUNICIPALITIES,
                settings=settings,
                statuses=OrderStatus.ALL_STATUSES,
                status_labels=OrderStatus.LABELS,
                payment_methods=PaymentMethod.ALL_METHODS,
                payment_labels=PaymentMethod.LABELS
            )

        fiscal_data = {
            'fiscal_doc_type': request.form.get('fiscal_doc_type', 'CC'),
            'fiscal_doc_number': request.form.get('fiscal_doc_number', '').strip(),
            'fiscal_name': request.form.get('fiscal_name', '').strip() or shipping_data['recipient_name'],
            'fiscal_email': request.form.get('fiscal_email', '').strip() or (customer_user.email if customer_user else current_user.email)
        }

        initial_status = request.form.get('status', OrderStatus.CONFIRMED)
        payment_method = request.form.get('payment_method', PaymentMethod.SIMULATED_CASH_ON_DELIVERY)
        is_paid = request.form.get('is_paid') == 'on' or request.form.get('is_paid') == '1'
        notes = request.form.get('notes', '').strip()

        try:
            order = OrderService.create_manual_order(
                admin_user=current_user,
                customer_user=customer_user,
                items_data=items_data,
                shipping_data=shipping_data,
                initial_status=initial_status,
                payment_method=payment_method,
                notes=notes,
                fiscal_data=fiscal_data,
                is_paid=is_paid
            )
            flash(f"¡Pedido #{order.order_number} generado exitosamente desde el panel administrativo!", "success")
            return redirect(url_for('admin_orders.detail', order_id=order.id))
        except ValueError as e:
            flash(f"Error al generar el pedido: {str(e)}", "danger")
        except Exception:
            current_app.logger.exception("Error inesperado al generar pedido manual")
            flash("Error inesperado al generar el pedido. Intenta de nuevo.", "danger")

    return render_template(
        'admin/orders/create.html',
        products=products,
        customers=customers,
        municipalities=VALLE_DE_ABURRA_MUNICIPALITIES,
        settings=settings,
        statuses=OrderStatus.ALL_STATUSES,
        status_labels=OrderStatus.LABELS,
        payment_methods=PaymentMethod.ALL_METHODS,
        payment_labels=PaymentMethod.LABELS
    )

