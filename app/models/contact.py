from datetime import datetime, timezone
from app.extensions import db


class ContactMessage(db.Model):
    """Mensajes recibidos a través del formulario de contacto público."""
    __tablename__ = 'contact_messages'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True)
    subject = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<ContactMessage #{self.id} de {self.email} - {self.subject}>"
