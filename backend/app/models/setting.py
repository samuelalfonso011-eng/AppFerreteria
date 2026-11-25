from decimal import Decimal

from app.extensions import db
from app.utils.timeutils import money, utcnow


class StoreSetting(db.Model):
    """Datos comerciales e identificacion del responsable del tratamiento."""
    __tablename__ = "store_settings"

    id = db.Column(db.Integer, primary_key=True)
    store_name = db.Column(db.String(150), nullable=False, default="FerrePro")
    legal_name = db.Column(db.String(150), nullable=False, default="FerrePro S.A.S.")
    nit = db.Column(db.String(30), nullable=False, default="")
    address = db.Column(db.String(255), nullable=False, default="Calle 50 # 45-20, Medellín, Antioquia")
    phone = db.Column(db.String(50), nullable=False, default="+57 300 000 0000")
    email = db.Column(db.String(254), nullable=False, default="privacidad@ferrepro.example")
    business_hours = db.Column(db.String(255), nullable=False,
                               default="Lunes a viernes de 7:00 a. m. a 6:00 p. m. Sábados de 7:00 a. m. a 2:00 p. m.")
    shipping_cost = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("15000"))
    free_shipping_threshold = db.Column(db.Numeric(12, 2), default=Decimal("300000"))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.CheckConstraint("shipping_cost >= 0", name="check_setting_shipping"),
    )

    @classmethod
    def get(cls):
        """Fila activa o, si aun no existe, una instancia con valores por defecto sin persistir."""
        setting = cls.query.order_by(cls.id).first()
        if setting is None:
            setting = cls(store_name="FerrePro", legal_name="FerrePro S.A.S.", nit="",
                          address="Calle 50 # 45-20, Medellín, Antioquia", phone="+57 300 000 0000",
                          email="privacidad@ferrepro.example",
                          business_hours="Lunes a viernes de 7:00 a. m. a 6:00 p. m.",
                          shipping_cost=Decimal("15000"), free_shipping_threshold=Decimal("300000"))
        return setting

    def calculate_shipping(self, subtotal):
        if self.free_shipping_threshold and subtotal >= self.free_shipping_threshold:
            return Decimal("0")
        return Decimal(self.shipping_cost)

    def to_public(self):
        return {
            "store_name": self.store_name,
            "legal_name": self.legal_name,
            "nit": self.nit,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "business_hours": self.business_hours,
            "shipping_cost": money(self.shipping_cost),
            "free_shipping_threshold": money(self.free_shipping_threshold) if self.free_shipping_threshold else None,
        }
