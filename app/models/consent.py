"""Evidencia mínima de autorización, sin duplicar correos, IP ni user-agent."""
from datetime import datetime, timezone
from app.extensions import db

POLICY_VERSION = '2026-11-13'


class PrivacyConsent(db.Model):
    __tablename__ = 'privacy_consents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    contact_message_id = db.Column(db.Integer, db.ForeignKey('contact_messages.id', ondelete='SET NULL'))
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='SET NULL'))
    purpose = db.Column(db.String(30), nullable=False)
    policy_version = db.Column(db.String(30), nullable=False, default=POLICY_VERSION)
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc))


def record_consent(purpose: str, **references) -> PrivacyConsent:
    """Participa de la transacción del formulario; no hace commit por su cuenta."""
    consent = PrivacyConsent(purpose=purpose, policy_version=POLICY_VERSION, **references)
    db.session.add(consent)
    return consent
