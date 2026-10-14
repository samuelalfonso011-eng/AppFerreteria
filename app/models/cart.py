from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class Cart(db.Model):
    """Carrito de compras persistente asociado a un usuario autenticado."""
    __tablename__ = 'carts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', back_populates='cart')
    items = db.relationship('CartItem', back_populates='cart', cascade='all, delete-orphan', lazy='joined')

    @property
    def total_items(self) -> int:
        """Cantidad total de unidades de productos en el carrito."""
        return sum(item.quantity for item in self.items)

    @property
    def subtotal(self) -> Decimal:
        """Calcula el subtotal basado en los precios actuales del servidor."""
        total = Decimal('0.00')
        for item in self.items:
            if item.product and item.product.is_active:
                total += Decimal(str(item.product.price)) * item.quantity
        return total

    def __repr__(self):
        return f"<Cart user_id={self.user_id} - items={self.total_items}>"


class CartItem(db.Model):
    """Ítems y cantidades dentro de un carrito."""
    __tablename__ = 'cart_items'

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cart_id', 'product_id', name='uq_cart_product'),
        db.CheckConstraint('quantity > 0', name='check_positive_cart_quantity'),
    )

    cart = db.relationship('Cart', back_populates='items')
    product = db.relationship('Product', back_populates='cart_items')

    @property
    def item_subtotal(self) -> Decimal:
        """Subtotal del artículo basado en el precio actual del producto."""
        if self.product:
            return Decimal(str(self.product.price)) * self.quantity
        return Decimal('0.00')

    def __repr__(self):
        return f"<CartItem cart={self.cart_id} product={self.product_id} qty={self.quantity}>"
