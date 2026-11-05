from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from app.services.cart_service import CartService
from app.models.setting import StoreSetting

cart_bp = Blueprint('cart', __name__, url_prefix='/carrito')


def _payload():
    """Devuelve (is_json, datos) tolerando cuerpos JSON vacíos o malformados."""
    if request.is_json:
        data = request.get_json(silent=True)
        return True, data if isinstance(data, dict) else {}
    return False, request.form


@cart_bp.route('/')
def view():
    """Vista detallada del carrito con subtotales y costos calculados en servidor."""
    cart_data = CartService.get_cart_data(current_user)
    settings = StoreSetting.get_settings()
    shipping_cost = settings.calculate_shipping(cart_data['subtotal'])
    total = cart_data['subtotal'] + shipping_cost

    return render_template(
        'cart/view.html',
        cart=cart_data,
        settings=settings,
        shipping_cost=shipping_cost,
        total=total
    )


@cart_bp.route('/agregar', methods=['POST'])
def add():
    """Agrega un producto al carrito comprobando existencias en servidor."""
    is_json, data = _payload()

    try:
        product_id = int(data.get('product_id'))
        quantity = int(data.get('quantity', 1))
    except (TypeError, ValueError):
        msg = "Parámetros de producto inválidos."
        if is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, "danger")
        return redirect(url_for('cart.view'))

    try:
        updated_cart = CartService.add_item(product_id, quantity, current_user)
        msg = "Producto añadido al carrito con éxito."
        if is_json:
            return jsonify({'success': True, 'message': msg, 'cart': {
                'total_items': updated_cart['total_items'],
                'subtotal': float(updated_cart['subtotal'])
            }})
        flash(msg, "success")
    except ValueError as e:
        if is_json:
            return jsonify({'success': False, 'message': str(e)}), 400
        flash(str(e), "warning")

    return redirect(request.referrer or url_for('cart.view'))


@cart_bp.route('/actualizar', methods=['POST'])
def update():
    """Actualiza la cantidad de un ítem en el carrito."""
    is_json, data = _payload()

    try:
        product_id = int(data.get('product_id'))
        quantity = int(data.get('quantity'))
    except (TypeError, ValueError):
        msg = "Datos de cantidad incorrectos."
        if is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, "danger")
        return redirect(url_for('cart.view'))

    try:
        updated_cart = CartService.update_quantity(product_id, quantity, current_user)
        msg = "Cantidad actualizada."
        if is_json:
            return jsonify({'success': True, 'message': msg, 'cart': {
                'total_items': updated_cart['total_items'],
                'subtotal': float(updated_cart['subtotal'])
            }})
        flash(msg, "info")
    except ValueError as e:
        if is_json:
            return jsonify({'success': False, 'message': str(e)}), 400
        flash(str(e), "warning")

    return redirect(url_for('cart.view'))


@cart_bp.route('/eliminar', methods=['POST'])
def remove():
    """Elimina un artículo del carrito."""
    is_json, data = _payload()

    try:
        product_id = int(data.get('product_id'))
    except (TypeError, ValueError):
        if is_json:
            return jsonify({'success': False, 'message': "ID inválido."}), 400
        return redirect(url_for('cart.view'))

    updated_cart = CartService.remove_item(product_id, current_user)
    msg = "Artículo eliminado del carrito."
    if is_json:
        return jsonify({'success': True, 'message': msg, 'cart': {
            'total_items': updated_cart['total_items'],
            'subtotal': float(updated_cart['subtotal'])
        }})
    flash(msg, "info")
    return redirect(url_for('cart.view'))


@cart_bp.route('/vaciar', methods=['POST'])
def clear():
    """Vacía por completo el carrito."""
    CartService.clear_cart(current_user)
    flash("Tu carrito de compras ha sido vaciado.", "info")
    return redirect(url_for('cart.view'))
