from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class Product(db.Model):
    """Modelo de productos del catálogo de la ferretería."""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='RESTRICT'), nullable=False, index=True)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    technical_specs = db.Column(db.Text, nullable=True)  # Características técnicas
    price = db.Column(db.Numeric(12, 2), nullable=False)
    stock = db.Column(db.Integer, default=0, nullable=False)
    min_stock_alert = db.Column(db.Integer, default=5, nullable=False)
    image_path = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.CheckConstraint('price >= 0', name='check_positive_price'),
        db.CheckConstraint('stock >= 0', name='check_non_negative_stock'),
        db.CheckConstraint('min_stock_alert >= 0', name='check_non_negative_min_stock'),
    )

    # Relaciones
    category = db.relationship('Category', back_populates='products')
    inventory_movements = db.relationship('InventoryMovement', back_populates='product', cascade='all, delete-orphan', lazy='dynamic')
    order_items = db.relationship('OrderItem', back_populates='product', lazy='dynamic')
    cart_items = db.relationship('CartItem', back_populates='product', cascade='all, delete-orphan', lazy='dynamic')

    @property
    def is_in_stock(self) -> bool:
        """Determina si el producto está disponible para la venta."""
        return self.is_active and self.stock > 0

    @property
    def is_low_stock(self) -> bool:
        """Indica si el inventario está en o por debajo del umbral mínimo."""
        return self.stock <= self.min_stock_alert

    @property
    def display_image(self) -> str:
        """Ruta de la imagen o placeholder/ilustración de categoría por defecto."""
        if self.image_path:
            return f"uploads/products/{self.image_path}"
        
        # Mapeo a ilustraciones vectoriales temáticas por categoría
        if self.category and self.category.slug:
            slug = self.category.slug.lower()
            if 'herramienta' in slug:
                return "img/temp/herramientas.svg"
            if 'electric' in slug:
                return "img/temp/electricidad.svg"
            if 'plomer' in slug or 'tubo' in slug or 'tuber' in slug:
                return "img/temp/plomeria.svg"
            if 'construc' in slug:
                return "img/temp/construccion.svg"
            if 'pintur' in slug:
                return "img/temp/pintura.svg"
            if 'segur' in slug:
                return "img/temp/seguridad.svg"
                
        return "img/placeholder-product.svg"

    def __repr__(self):
        return f"<Product {self.sku} - {self.name} - ${self.price}>"
