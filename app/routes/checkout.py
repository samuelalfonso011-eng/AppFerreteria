import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import Address
from app.models.order import Order, OrderStatus
from app.models.payment import PaymentMethod
from app.models.setting import StoreSetting
from app.forms.checkout_forms import CheckoutForm, PaymentSimulationForm
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.payment_service import payment_service

checkout_bp = Blueprint('checkout', __name__, url_prefix='/checkout')


@checkout_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Paso 1 del Checkout: Datos de entrega y revisión de subtotales."""
    cart_data = CartService.get_cart_data(current_user)
    if not cart_data['items']:
        flash("Tu carrito está vacío. Agrega productos antes de realizar el pedido.", "warning")
        return redirect(url_for('cart.view'))

    settings = StoreSetting.get_settings()
    shipping_cost = settings.calculate_shipping(cart_data['subtotal'])
    total = cart_data['subtotal'] + shipping_cost

    # Direcciones guardadas del cliente
    user_addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc()).all()

    form = CheckoutForm()
    form.saved_address_id.choices = [(0, "Ingresar una nueva dirección")] + [
        (a.id, f"{a.recipient_name} - {a.street_address}, {a.city} ({a.neighborhood})") for a in user_addresses
    ]

    # Generar token de idempotencia si no viene en el formulario
    if request.method == 'GET':
        form.idempotency_key.data = f"IDEMP-{current_user.id}-{uuid.uuid4().hex}"
        # Pre-llenar con la dirección predeterminada si existe
        default_addr = next((a for a in user_addresses if a.is_default), None) or (user_addresses[0] if user_addresses else None)
        if default_addr:
            form.saved_address_id.data = default_addr.id
            form.recipient_name.data = default_addr.recipient_name
            form.phone.data = default_addr.phone
            form.department.data = default_addr.department
            form.city.data = default_addr.city
            form.neighborhood.data = default_addr.neighborhood
            form.street_address.data = default_addr.street_address
            form.complement.data = default_addr.complement
            form.delivery_instructions.data = default_addr.delivery_instructions

    if form.validate_on_submit():
        # Resolver datos de entrega
        saved_id = form.saved_address_id.data
        if saved_id and saved_id > 0:
            addr = Address.query.filter_by(id=saved_id, user_id=current_user.id).first()
            if addr:
                shipping_data = {
                    'recipient_name': addr.recipient_name,
                    'phone': addr.phone,
                    'department': addr.department,
                    'city': addr.city,
                    'neighborhood': addr.neighborhood,
                    'street_address': addr.street_address,
                    'complement': addr.complement,
                    'delivery_instructions': addr.delivery_instructions,
                }
            else:
                flash("La dirección seleccionada no es válida.", "danger")
                return redirect(url_for('checkout.index'))
        else:
            shipping_data = {
                'recipient_name': form.recipient_name.data.strip(),
                'phone': form.phone.data.strip(),
                'department': form.department.data.strip(),
                'city': form.city.data.strip(),
                'neighborhood': form.neighborhood.data.strip(),
                'street_address': form.street_address.data.strip(),
                'complement': form.complement.data.strip() if form.complement.data else None,
                'delivery_instructions': form.delivery_instructions.data.strip() if form.delivery_instructions.data else None,
            }

            # Guardar en la libreta si el cliente lo solicitó
            if form.save_to_address_book.data:
                new_saved = Address(
                    user_id=current_user.id,
                    is_default=(len(user_addresses) == 0),
                    **shipping_data
                )
                db.session.add(new_saved)
                db.session.commit()

        # Crear orden transaccional con descuento de inventario
        try:
            order = OrderService.create_order(
                user=current_user,
                shipping_data=shipping_data,
                idempotency_key=form.idempotency_key.data,
                notes=form.notes.data.strip() if form.notes.data else None
            )
            flash("Pedido registrado con éxito. Por favor completa el pago de prueba.", "info")
            return redirect(url_for('checkout.payment_view', order_number=order.order_number))
        except Exception as e:
            flash(f"Error al procesar el pedido: {str(e)}", "danger")
            return redirect(url_for('cart.view'))

    return render_template(
        'checkout/checkout.html',
        form=form,
        cart=cart_data,
        settings=settings,
        shipping_cost=shipping_cost,
        total=total,
        addresses=user_addresses
    )


@checkout_bp.route('/pago/<order_number>', methods=['GET'])
@login_required
def payment_view(order_number):
    """Paso 2 del Checkout: Interfaz de pago en modo de prueba."""
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()

    # Si la orden ya está confirmada, redirigir a confirmación
    if order.status != OrderStatus.PENDING_CONFIRMATION:
        return redirect(url_for('checkout.confirmation', order_number=order.order_number))

    form = PaymentSimulationForm()
    return render_template('checkout/payment_simulation.html', order=order, form=form)


@checkout_bp.route('/procesar-pago/<order_number>', methods=['POST'])
@login_required
def process_simulated_payment(order_number):
    """Procesa la transacción simulada en el servidor (aprobada, rechazada o pendiente)."""
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    form = PaymentSimulationForm()

    if form.validate_on_submit():
        method = form.payment_method.data
        action = form.simulated_action.data

        try:
            payment = payment_service.process_payment(
                order=order,
                payment_method=method,
                simulated_action=action
            )

            if payment.status == 'APPROVED':
                flash("¡Pago de prueba aprobado exitosamente! Tu pedido ha sido confirmado.", "success")
                return redirect(url_for('checkout.confirmation', order_number=order.order_number))
            elif payment.status == 'REJECTED':
                flash("El pago de prueba fue rechazado según la simulación seleccionada. Puedes intentar nuevamente con otro método.", "danger")
                return redirect(url_for('checkout.payment_view', order_number=order.order_number))
            else:
                flash("El pago de prueba quedó en estado pendiente de verificación.", "warning")
                return redirect(url_for('checkout.confirmation', order_number=order.order_number))

        except Exception as e:
            flash(f"Error en la simulación de pago: {str(e)}", "danger")
            return redirect(url_for('checkout.payment_view', order_number=order.order_number))

    return redirect(url_for('checkout.payment_view', order_number=order.order_number))


@checkout_bp.route('/confirmacion/<order_number>')
@login_required
def confirmation(order_number):
    """Paso 3 del Checkout: Comprobante y resumen de orden confirmada."""
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    latest_payment = order.payments.order_by(order.payments.property.mapper.class_.created_at.desc()).first()

    return render_template(
        'checkout/confirmation.html',
        order=order,
        latest_payment=latest_payment
    )
