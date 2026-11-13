from datetime import datetime, timezone
import hashlib
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class Role(db.Model):
    """Roles de acceso en el sistema (ej. 'admin', 'customer')."""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)

    users = db.relationship('User', back_populates='role', lazy='dynamic')

    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    """Modelo de usuarios autenticados del sistema."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete='RESTRICT'), nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relaciones
    role = db.relationship('Role', back_populates='users')
    addresses = db.relationship('Address', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')
    orders = db.relationship('Order', back_populates='user', lazy='dynamic')
    cart = db.relationship('Cart', back_populates='user', uselist=False, cascade='all, delete-orphan')

    @property
    def session_fingerprint(self) -> str:
        """Revoca también cookies de recordar sesión al cambiar la contraseña."""
        return hashlib.sha256(self.password_hash.encode()).hexdigest()

    def get_id(self) -> str:
        return f"{self.id}:{self.session_fingerprint}"

    def set_password(self, password: str):
        """Genera hash seguro para la contraseña."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica la contraseña contra el hash almacenado."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        """Indica si el usuario tiene rol de administrador."""
        return self.role and self.role.name == 'admin'

    def __repr__(self):
        return f"<User {self.email} - Role: {self.role.name if self.role else 'None'}>"


class Address(db.Model):
    """Direcciones de entrega guardadas en el perfil del cliente."""
    __tablename__ = 'addresses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    recipient_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    neighborhood = db.Column(db.String(100), nullable=False)
    street_address = db.Column(db.String(255), nullable=False)
    complement = db.Column(db.String(100), nullable=True)
    delivery_instructions = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', back_populates='addresses')

    def formatted_address(self) -> str:
        """Dirección formateada para visualización."""
        parts = [self.street_address]
        if self.complement:
            parts.append(self.complement)
        parts.extend([self.neighborhood, self.city, self.department])
        return ", ".join(parts)

    def __repr__(self):
        return f"<Address {self.recipient_name} - {self.city}>"
