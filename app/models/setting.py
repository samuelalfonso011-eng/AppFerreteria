from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class StoreSetting(db.Model):
    """Configuraciones comerciales e institucionales de la ferretería."""
    __tablename__ = 'store_settings'

    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(150), default='Ferretería El Constructor', nullable=False)
    phone = db.Column(db.String(50), default='300 000 0000', nullable=False)
    email = db.Column(db.String(100), default='contacto@ferreteriaelconstructor.com', nullable=False)
    address = db.Column(db.String(255), default='Calle 50 # 45-20, Medellín, Colombia', nullable=False)
    business_hours = db.Column(db.String(255), default='Lunes a Viernes: 7:00 AM - 6:00 PM | Sábados: 7:00 AM - 2:00 PM', nullable=False)
    default_shipping_cost = db.Column(db.Numeric(12, 2), default=Decimal('10000.00'), nullable=False)
    free_shipping_threshold = db.Column(db.Numeric(12, 2), default=Decimal('200000.00'), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    @classmethod
    def get_settings(cls):
        """Retorna la configuración activa o crea una fila por defecto si la tabla está vacía."""
        setting = cls.query.first()
        if not setting:
            setting = cls()
            db.session.add(setting)
            db.session.commit()
        return setting

    def calculate_shipping(self, subtotal: Decimal) -> Decimal:
        """Calcula el costo de entrega según el umbral de envío gratuito configurado."""
        if self.free_shipping_threshold and subtotal >= self.free_shipping_threshold:
            return Decimal('0.00')
        return self.default_shipping_cost

    def __repr__(self):
        return f"<StoreSetting {self.store_name}>"
