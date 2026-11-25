from app.extensions import db
from app.utils.timeutils import iso, money, utcnow

# Ilustraciones vectoriales disponibles en el frontend (index.html / app.js)
ART_KEYS = ("drill", "saw", "wrench", "roller", "lamp", "helmet")


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    headline = db.Column(db.String(120))  # Titular del mosaico de la portada; vacio = no aparece
    art = db.Column(db.String(20), nullable=False, default="wrench")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    products = db.relationship("Product", back_populates="category")

    def to_public(self):
        return {"id": self.id, "name": self.name, "slug": self.slug,
                "headline": self.headline, "art": self.art}

    def to_admin(self, product_count=0):
        data = self.to_public()
        data.update({"sort_order": self.sort_order, "is_active": self.is_active,
                     "product_count": product_count})
        return data


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"),
                            nullable=False, index=True)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    specs = db.Column(db.Text)  # Una caracteristica tecnica por linea
    price = db.Column(db.Numeric(12, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    min_stock_alert = db.Column(db.Integer, nullable=False, default=5)
    art = db.Column(db.String(20), nullable=False, default="wrench")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.CheckConstraint("price >= 0", name="check_product_price"),
        db.CheckConstraint("stock >= 0", name="check_product_stock"),
        db.CheckConstraint("min_stock_alert >= 0", name="check_product_min_stock"),
    )

    category = db.relationship("Category", back_populates="products", lazy="joined")
    movements = db.relationship("InventoryMovement", back_populates="product",
                                cascade="all, delete-orphan", lazy="dynamic")

    @property
    def is_low_stock(self):
        return self.stock <= self.min_stock_alert

    @property
    def spec_lines(self):
        return [line.strip() for line in (self.specs or "").splitlines() if line.strip()]

    def to_public(self):
        return {
            "id": self.id,
            "sku": self.sku,
            "slug": self.slug,
            "name": self.name,
            "category": self.category.name if self.category else None,
            "category_slug": self.category.slug if self.category else None,
            "description": self.description or "",
            "specs": self.spec_lines,
            "price": money(self.price),
            "stock": self.stock,
            "available": self.stock > 0,
            "art": self.art,
        }

    def to_admin(self):
        data = self.to_public()
        data.update({
            "category_id": self.category_id,
            "specs_text": self.specs or "",
            "min_stock_alert": self.min_stock_alert,
            "is_low_stock": self.is_low_stock,
            "is_active": self.is_active,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        })
        return data
