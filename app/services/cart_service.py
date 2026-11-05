from decimal import Decimal
from flask import session
from app.extensions import db
from app.models.product import Product
from app.models.cart import Cart, CartItem


class CartService:
    """
    Servicio de gestión de carrito de compras.
    Soporta usuarios autenticados (persistencia en PostgreSQL) y visitantes (sesión de Flask),
    con validación obligatoria de stock y recálculo estricto de precios en el servidor.
    """

    SESSION_KEY = 'guest_cart'
    MAX_CART_LINES = 100  # evita que la cookie de sesión del invitado crezca sin límite

    @classmethod
    def _get_or_create_user_cart(cls, user_id: int) -> Cart:
        cart = Cart.query.filter_by(user_id=user_id).first()
        if not cart:
            cart = Cart(user_id=user_id)
            db.session.add(cart)
            db.session.commit()
        return cart

    @classmethod
    def get_cart_data(cls, user=None) -> dict:
        """
        Retorna la estructura normalizada del carrito con precios vigentes desde la base de datos.
        Nunca confía en precios enviados por el cliente.
        """
        items = []
        total_items = 0
        subtotal = Decimal('0.00')

        if user and user.is_authenticated:
            from sqlalchemy.orm import joinedload
            cart = Cart.query.options(joinedload(Cart.items).joinedload(CartItem.product)).filter_by(user_id=user.id).first()
            if cart:
                for ci in cart.items:
                    product = ci.product
                    if product and product.is_active:
                        item_subtotal = Decimal(str(product.price)) * ci.quantity
                        subtotal += item_subtotal
                        total_items += ci.quantity
                        items.append({
                            'product_id': product.id,
                            'name': product.name,
                            'sku': product.sku,
                            'price': Decimal(str(product.price)),
                            'quantity': ci.quantity,
                            'subtotal': item_subtotal,
                            'stock': product.stock,
                            'image': product.display_image,
                            'is_available': product.stock >= ci.quantity
                        })
        else:
            # Carrito de invitado en sesión: consulta en bloque O(N) evitando consultas en bucle
            guest_cart = session.get(cls.SESSION_KEY, {})
            valid_pids = []
            for pid_str in guest_cart.keys():
                try:
                    valid_pids.append(int(pid_str))
                except (ValueError, TypeError):
                    continue

            if valid_pids:
                products_list = Product.query.filter(Product.id.in_(valid_pids)).all()
                products_map = {p.id: p for p in products_list}
            else:
                products_map = {}

            for product_id in valid_pids:
                qty = guest_cart.get(str(product_id), guest_cart.get(product_id, 0))
                if not qty or qty <= 0:
                    continue
                product = products_map.get(product_id)
                if product and product.is_active:
                    item_subtotal = Decimal(str(product.price)) * qty
                    subtotal += item_subtotal
                    total_items += qty
                    items.append({
                        'product_id': product.id,
                        'name': product.name,
                        'sku': product.sku,
                        'price': Decimal(str(product.price)),
                        'quantity': qty,
                        'subtotal': item_subtotal,
                        'stock': product.stock,
                        'image': product.display_image,
                        'is_available': product.stock >= qty
                    })

        return {
            'items': items,
            'items_list': items,
            'total_items': total_items,
            'subtotal': subtotal
        }

    @classmethod
    def add_item(cls, product_id: int, quantity: int = 1, user=None) -> dict:
        """Agrega o incrementa un producto en el carrito validando el stock actual."""
        if quantity <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")

        product = db.session.get(Product, product_id)
        if not product or not product.is_active:
            raise ValueError("El producto no existe o está desactivado.")

        if user and user.is_authenticated:
            cart = cls._get_or_create_user_cart(user.id)
            cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()

            current_qty = cart_item.quantity if cart_item else 0
            new_qty = current_qty + quantity

            if new_qty > product.stock:
                raise ValueError(f"Solo hay {product.stock} unidades disponibles en existencias.")

            if cart_item:
                cart_item.quantity = new_qty
            else:
                cart_item = CartItem(cart_id=cart.id, product_id=product.id, quantity=new_qty)
                db.session.add(cart_item)

            db.session.commit()
        else:
            guest_cart = session.get(cls.SESSION_KEY, {})
            pid_str = str(product_id)
            if pid_str not in guest_cart and len(guest_cart) >= cls.MAX_CART_LINES:
                raise ValueError(f"El carrito admite hasta {cls.MAX_CART_LINES} productos distintos.")
            current_qty = guest_cart.get(pid_str, 0)
            new_qty = current_qty + quantity

            if new_qty > product.stock:
                raise ValueError(f"Solo hay {product.stock} unidades disponibles en existencias.")

            guest_cart[pid_str] = new_qty
            session[cls.SESSION_KEY] = guest_cart
            session.modified = True

        return cls.get_cart_data(user)

    @classmethod
    def update_quantity(cls, product_id: int, quantity: int, user=None) -> dict:
        """Modifica la cantidad exacta de un artículo en el carrito."""
        if quantity <= 0:
            return cls.remove_item(product_id, user)

        product = db.session.get(Product, product_id)
        if not product or not product.is_active:
            raise ValueError("El producto no está disponible.")

        if quantity > product.stock:
            raise ValueError(f"Solo hay {product.stock} unidades disponibles en existencias.")

        if user and user.is_authenticated:
            cart = cls._get_or_create_user_cart(user.id)
            cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
            if not cart_item:
                raise ValueError("Ese producto no está en tu carrito.")
            cart_item.quantity = quantity
            db.session.commit()
        else:
            guest_cart = session.get(cls.SESSION_KEY, {})
            pid_str = str(product_id)
            if pid_str not in guest_cart:
                raise ValueError("Ese producto no está en tu carrito.")
            guest_cart[pid_str] = quantity
            session[cls.SESSION_KEY] = guest_cart
            session.modified = True

        return cls.get_cart_data(user)

    @classmethod
    def remove_item(cls, product_id: int, user=None) -> dict:
        """Elimina un producto del carrito."""
        if user and user.is_authenticated:
            cart = Cart.query.filter_by(user_id=user.id).first()
            if cart:
                CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).delete()
                db.session.commit()
        else:
            guest_cart = session.get(cls.SESSION_KEY, {})
            pid_str = str(product_id)
            if pid_str in guest_cart:
                del guest_cart[pid_str]
                session[cls.SESSION_KEY] = guest_cart
                session.modified = True

        return cls.get_cart_data(user)

    @classmethod
    def clear_cart(cls, user=None):
        """Vacía por completo el carrito de compras."""
        if user and user.is_authenticated:
            cart = Cart.query.filter_by(user_id=user.id).first()
            if cart:
                CartItem.query.filter_by(cart_id=cart.id).delete()
                db.session.commit()
        else:
            session.pop(cls.SESSION_KEY, None)
            session.modified = True

    @classmethod
    def sync_guest_cart_to_user(cls, user):
        """Sincroniza los artículos del carrito de invitado al registrarse o iniciar sesión."""
        guest_cart = session.get(cls.SESSION_KEY, {})
        if not guest_cart:
            return

        cart = cls._get_or_create_user_cart(user.id)

        for pid_str, guest_qty in guest_cart.items():
            try:
                product_id = int(pid_str)
                product = db.session.get(Product, product_id)
                if not product or not product.is_active:
                    continue

                cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
                if cart_item:
                    combined_qty = cart_item.quantity + guest_qty
                    cart_item.quantity = min(combined_qty, product.stock)
                else:
                    qty_to_set = min(guest_qty, product.stock)
                    if qty_to_set > 0:
                        new_item = CartItem(cart_id=cart.id, product_id=product.id, quantity=qty_to_set)
                        db.session.add(new_item)
            except (ValueError, TypeError):
                continue

        db.session.commit()
        session.pop(cls.SESSION_KEY, None)
        session.modified = True
