import hashlib

from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.utils.timeutils import iso, utcnow


class User(db.Model):
    """Cuentas con acceso a la plataforma. Los permisos dependen del rol."""
    __tablename__ = "users"

    ROLE_ADMIN = "admin"
    ROLE_EMPLOYEE = "employee"
    ROLE_CUSTOMER = "customer"
    ROLES = (ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_CUSTOMER)

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_CUSTOMER)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    email_verification_pending = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        db.Index("uq_users_normalized_email", func.lower(func.trim(email)), unique=True),
        db.CheckConstraint("role IN ('admin', 'employee', 'customer')", name="check_user_role"),
    )

    @classmethod
    def by_email(cls, email):
        return cls.query.filter(func.lower(func.trim(cls.email)) == email.strip().lower()).one_or_none()

    @property
    def fingerprint(self):
        """Cambia con la contrasena: al cambiarla, todas las sesiones abiertas quedan invalidas."""
        return hashlib.sha256(self.password_hash.encode("utf-8")).hexdigest()

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_staff(self):
        return self.role in (self.ROLE_ADMIN, self.ROLE_EMPLOYEE)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_session(self):
        return {
            "name": self.full_name,
            "email": self.email,
            "role": self.role,
            "last_login_at": iso(self.last_login_at),
        }


class AuthSession(db.Model):
    __tablename__ = "auth_sessions"

    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = db.Column(db.BigInteger, nullable=False, index=True)
