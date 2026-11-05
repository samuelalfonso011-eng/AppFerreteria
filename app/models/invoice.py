from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class ElectronicInvoice(db.Model):
    """
    Modelo de Factura Electrónica de Venta según el estándar de la DIAN (Colombia).
    Registra el consecutivo autorizado FE-XXXX, CUFE (SHA-384), desglose de IVA (19%) y QR de validación.
    """
    __tablename__ = 'electronic_invoices'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)  # ej: FE-0001
    cufe = db.Column(db.String(128), unique=True, nullable=False, index=True)

    # Datos del Emisor (Ferretería El Constructor)
    issuer_nit = db.Column(db.String(50), default="901.845.120-3", nullable=False)
    issuer_name = db.Column(db.String(150), default="Ferretería El Constructor S.A.S.", nullable=False)
    issuer_address = db.Column(db.String(255), default="Calle 50 # 45-20, Medellín, Antioquia", nullable=False)
    issuer_phone = db.Column(db.String(50), default="(+57) 300 000 0000", nullable=False)
    dian_resolution = db.Column(db.String(150), default="Resolución DIAN No. 18764000001 de 2026. Rango: FE-0001 a FE-9999", nullable=False)

    # Datos del Adquirente (Cliente)
    customer_doc_type = db.Column(db.String(20), default="CC", nullable=False)
    customer_doc_number = db.Column(db.String(50), nullable=False)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_email = db.Column(db.String(150), nullable=False)

    # Desglose fiscal y monetario
    base_amount = db.Column(db.Numeric(12, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)  # IVA 19%
    tax_rate = db.Column(db.Numeric(5, 2), default=Decimal('19.00'), nullable=False)
    shipping_cost = db.Column(db.Numeric(12, 2), default=Decimal('0.00'), nullable=False)
    total = db.Column(db.Numeric(12, 2), nullable=False)

    # Código QR y metadatos DIAN
    qr_svg = db.Column(db.Text, nullable=True)
    qr_data = db.Column(db.Text, nullable=True)

    issued_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relación bidireccional con Order
    order = db.relationship('Order', back_populates='invoice')

    def __repr__(self):
        return f"<ElectronicInvoice {self.invoice_number} CUFE:{self.cufe[:12]}... Total:${self.total}>"
