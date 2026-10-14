from datetime import datetime, timezone
import re
from app.extensions import db


def generate_slug(text: str) -> str:
    """Genera un slug normalizado apto para URLs."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '-', text)


class Category(db.Model):
    """Categorías de productos de la ferretería."""
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    products = db.relationship('Product', back_populates='category', lazy='dynamic')

    @classmethod
    def normalize_name(cls, name: str) -> str:
        """Normaliza el nombre eliminando espacios múltiples."""
        return " ".join(name.strip().split())

    def __repr__(self):
        return f"<Category {self.name}>"
