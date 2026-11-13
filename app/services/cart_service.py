from decimal import Decimal
from flask import session
from app.extensions import db
from app.models.product import Product
from app.models.cart import Cart, CartItem
from sqlalchemy.orm import joinedload


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
    def _guest_quantities(cls) -> dict[int, int]:
        """Normaliza la cookie firmada y descarta valores de versiones antiguas inválidos."""
        raw = session.get(cls.SESSION_KEY, {})
        if not isinstance(raw, dict):
            return {}
        quantities = {}
        for key, quantity in list(raw.items())[:cls.MAX_CART_LINES]:
            try:
                product_id = int(key)
            except (ValueError, TypeError):
                continue
            if product_id > 0 and type(quantity) is int and quantity > 0:
                quantities[product_id] = quantity
        return quantities

    @staticmethod
    def _serialize_item(product: Product, quantity: int) -> dict:
        price = Decimal(str(product.price))
        return {
            'product_id': product.id, 'name': product.name, 'sku': product.sku,
            'price': price, 'quantity': quantity, 'subtotal': price * quantity,
            'stock': product.stock, 'image': product.display_image,
            'is_available': product.stock >= quantity,
        }

    @classmethod
    def get_cart_data(cls, user=None) -> dict:
        """Precios del servidor y carga anticipada, sin consultas por artículo."""
        if user and user.is_authenticated:
            cart = Cart.query.options(joinedload(Cart.items).joinedload(CartItem.product)
                                      .joinedload(Product.category)).filter_by(user_id=user.id).first()
            pairs = ((item.product, item.quantity) for item in cart.items) if cart else ()
        else:
            quantities = cls._guest_quantities()
            products = Product.query.options(joinedload(Product.category)).filter(
                Product.id.in_(quantities)).all() if quantities else []
            pairs = ((product, quantities[product.id]) for product in products)
        items = [cls._serialize_item(product, quantity) for product, quantity in pairs
                 if product and product.is_active and quantity > 0]
        return {
            'items': items, 'items_list': items,
            'total_items': sum(item['quantity'] for item in items),
            'subtotal': sum((item['subtotal'] for item in items), Decimal('0.00')),
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
    def clear_cart(cls, user=None, *, commit: bool = True):
        """Vacía por completo el carrito de compras."""
        if user and user.is_authenticated:
            cart = Cart.query.filter_by(user_id=user.id).first()
            if cart:
                CartItem.query.filter_by(cart_id=cart.id).delete()
                if commit:
                    db.session.commit()
        else:
            session.pop(cls.SESSION_KEY, None)
            session.modified = True

    @classmethod
    def sync_guest_cart_to_user(cls, user):
        """Sincroniza los artículos del carrito de invitado al registrarse o iniciar sesión."""
        quantities = cls._guest_quantities()
        if not quantities:
            session.pop(cls.SESSION_KEY, None)
            return
        cart = cls._get_or_create_user_cart(user.id)

        products = Product.query.filter(Product.id.in_(quantities), Product.is_active.is_(True)).all()
        existing_items = {item.product_id: item for item in cart.items}
        for product in products:
            cart_item = existing_items.get(product.id)
            quantity = min((cart_item.quantity if cart_item else 0) + quantities[product.id], product.stock)
            if cart_item and quantity <= 0:
                db.session.delete(cart_item)
            elif cart_item:
                cart_item.quantity = quantity
            elif quantity > 0:
                db.session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity))

        db.session.commit()
        session.pop(cls.SESSION_KEY, None)
        session.modified = True
