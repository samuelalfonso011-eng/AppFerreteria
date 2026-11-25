"""Evidencia de autorizacion (Ley 1581 de 2012, art. 9; Decreto 1074 de 2015).

Se guarda la finalidad, el documento aceptado, su version y la fecha y hora. El checkout registra la IP observada por el servidor.
"""
from app.extensions import db
from app.legal.content import POLICY_VERSION
from app.utils.timeutils import iso, utcnow


class PrivacyConsent(db.Model):
    __tablename__ = "privacy_consents"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    ip_address = db.Column(db.String(45))
    purpose = db.Column(db.String(30), nullable=False)    # checkout, registro, contacto
    document = db.Column(db.String(30), nullable=False)   # terms, habeas_data
    policy_version = db.Column(db.String(20), nullable=False)
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self):
        return {"purpose": self.purpose, "document": self.document,
                "policy_version": self.policy_version, "accepted_at": iso(self.accepted_at)}


def record_consent(purpose, document, accepted_at=None, **references):
    """Participa de la transaccion del llamador; no hace commit."""
    consent = PrivacyConsent(purpose=purpose, document=document, policy_version=POLICY_VERSION,
                             accepted_at=accepted_at or utcnow(), **references)
    db.session.add(consent)
    return consent
