import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models.invoice import ElectronicInvoice
from app.models.order import Order
from app.utils.timezone import now_bogota, format_bogota


class InvoiceService:
    """Comprobantes de simulación. No implementa factura electrónica ni validación DIAN."""

    ISSUER_NIT = "DEMO-SIN-NIT"
    ISSUER_NAME = "Tienda de demostración"
    ISSUER_ADDRESS = "Dirección de demostración"
    ISSUER_PHONE = "Sin teléfono fiscal configurado"
    ISSUER_EMAIL = ""
    DIAN_RESOLUTION = "SIMULACIÓN: sin resolución ni autorización DIAN"

    @classmethod
    def generate_invoice_number(cls) -> str:
        """Genera el siguiente consecutivo de factura electrónica FE-0001."""
        # Se parte del último consecutivo emitido (no de COUNT, que repite números si hay huecos)
        last = ElectronicInvoice.query.order_by(ElectronicInvoice.id.desc()).first()
        last_n = 0
        if last:
            try:
                last_n = int(last.invoice_number.split("-")[-1])
            except ValueError:
                last_n = ElectronicInvoice.query.count()
        return f"FE-{last_n + 1:04d}"

    @classmethod
    def calculate_taxes(cls, subtotal: Decimal) -> tuple[Decimal, Decimal]:
        """
        Calcula la base gravable y el IVA (19%) para productos ferreteros con precios brutos incluidos.
        Retorna: (base_imponible, iva_19)
        """
        subtotal_dec = Decimal(str(subtotal))
        base = (subtotal_dec / Decimal('1.19')).quantize(Decimal('0.01'))
        tax = (subtotal_dec - base).quantize(Decimal('0.01'))
        return base, tax

    @classmethod
    def calculate_cufe(cls, invoice_num: str, issued_date_str: str, doc_number: str, total_str: str, tax_str: str) -> str:
        """
        Calcula el Código Único de Factura Electrónica (CUFE) mediante SHA-384
        solo como referencia interna de simulación, sin validez fiscal.
        """
        raw_string = f"{invoice_num}{issued_date_str}{cls.ISSUER_NIT}{doc_number}{total_str}{tax_str}SIMULATION-NOT-A-FISCAL-INVOICE"
        return hashlib.sha384(raw_string.encode('utf-8')).hexdigest()

    @classmethod
    def generate_qr_svg(cls, qr_text: str) -> str:
        """Marcador de demostración estático; no simula un QR verificable."""
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 60"><text x="10" y="35">SIMULACIÓN</text></svg>'

    @classmethod
    def get_or_create_invoice_for_order(cls, order: Order) -> ElectronicInvoice:
        """
        Genera o recupera la Factura Electrónica de Venta para un pedido aprobado.
        """
        if order.invoice:
            return order.invoice

        for attempt in range(5):
            try:
                return cls._create_invoice(order)
            except IntegrityError:
                # Carrera: otro proceso tomó el mismo consecutivo o ya facturó este pedido
                db.session.rollback()
                existing = ElectronicInvoice.query.filter_by(order_id=order.id).first()
                if existing:
                    return existing
        raise RuntimeError("No fue posible asignar un consecutivo de factura tras varios intentos.")

    @classmethod
    def _create_invoice(cls, order: Order) -> ElectronicInvoice:
        invoice_num = cls.generate_invoice_number()
        base_amount, tax_amount = cls.calculate_taxes(order.subtotal)

        # Determinar datos fiscales del adquirente
        doc_type = order.fiscal_doc_type or 'CC'
        doc_number = (order.fiscal_doc_number or '').strip()
        if not doc_number:
            # Consumidor final estándar DIAN si no se proveyó NIT/cédula
            doc_number = "222222222222" if doc_type == 'CC' else f"CC-{order.user.id}"

        cust_name = (order.fiscal_name or order.shipping_recipient_name or order.user.full_name).strip()
        cust_email = (order.fiscal_email or order.user.email).strip().lower()

        now_utc = datetime.now(timezone.utc)
        date_str_dian = format_bogota(now_utc, "%Y-%m-%d %H:%M:%S")

        total_str = f"{order.total:.2f}"
        tax_str = f"{tax_amount:.2f}"

        cufe = cls.calculate_cufe(
            invoice_num=invoice_num,
            issued_date_str=date_str_dian,
            doc_number=doc_number,
            total_str=total_str,
            tax_str=tax_str
        )

        qr_data = (
            f"NumFac={invoice_num}\n"
            f"FecFac={date_str_dian}\n"
            f"NitFac={cls.ISSUER_NIT}\n"
            f"DocAdq={doc_number}\n"
            f"ValFac={base_amount:.2f}\n"
            f"ValIva={tax_amount:.2f}\n"
            f"ValOtroIm=0.00\n"
            f"ValTotal={order.total:.2f}\n"
            f"CUFE={cufe}"
        )

        qr_svg = cls.generate_qr_svg(qr_data)

        invoice = ElectronicInvoice(
            order_id=order.id,
            invoice_number=invoice_num,
            cufe=cufe,
            issuer_nit=cls.ISSUER_NIT,
            issuer_name=cls.ISSUER_NAME,
            issuer_address=cls.ISSUER_ADDRESS,
            issuer_phone=cls.ISSUER_PHONE,
            dian_resolution=cls.DIAN_RESOLUTION,
            customer_doc_type=doc_type,
            customer_doc_number=doc_number,
            customer_name=cust_name,
            customer_email=cust_email,
            base_amount=base_amount,
            tax_amount=tax_amount,
            tax_rate=Decimal('19.00'),
            shipping_cost=order.shipping_cost,
            total=order.total,
            qr_svg=qr_svg,
            qr_data=qr_data,
            issued_at=now_utc
        )

        db.session.add(invoice)
        db.session.commit()
        return invoice
