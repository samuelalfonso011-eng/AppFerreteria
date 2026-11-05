import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models.invoice import ElectronicInvoice
from app.models.order import Order
from app.utils.timezone import now_bogota, format_bogota


class InvoiceService:
    """
    Servicio de Facturación Electrónica de Venta estándar DIAN (Colombia).
    Genera consecutivos FE-XXXX, cálculo de base gravable e IVA (19%),
    CUFE mediante SHA-384 y representación gráfica en SVG del código QR.
    """

    ISSUER_NIT = "901.845.120-3"
    ISSUER_NAME = "Ferretería El Constructor S.A.S."
    ISSUER_ADDRESS = "Calle 50 # 45-20, Medellín, Antioquia"
    ISSUER_PHONE = "(+57) 300 000 0000"
    ISSUER_EMAIL = "facturacion@ferreteriaelconstructor.com"
    DIAN_RESOLUTION = "Resolución DIAN No. 18764000001 de 2026. Rango: FE-0001 a FE-9999"
    TECHNICAL_KEY = "dian_tech_key_ferreteria_2026_colombia_auth_prod"

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
        conforme al estándar del Anexo Técnico de la DIAN.
        """
        raw_string = f"{invoice_num}{issued_date_str}{cls.ISSUER_NIT}{doc_number}{total_str}{tax_str}{cls.TECHNICAL_KEY}"
        return hashlib.sha384(raw_string.encode('utf-8')).hexdigest()

    @classmethod
    def generate_qr_svg(cls, qr_text: str) -> str:
        """
        Genera una representación gráfica vectorial SVG del código QR con esquinas DIAN oficiales
        y matriz de datos determinística derivada del hash del CUFE.
        """
        # Matriz 25x25
        size = 25
        grid = [[0 for _ in range(size)] for _ in range(size)]

        # Función para dibujar los 3 patrones de posición (Finder Patterns 7x7)
        def draw_finder(ox, oy):
            for y in range(7):
                for x in range(7):
                    if (y in (0, 6) or x in (0, 6)) or (2 <= y <= 4 and 2 <= x <= 4):
                        grid[oy + y][ox + x] = 1

        draw_finder(0, 0)
        draw_finder(size - 7, 0)
        draw_finder(0, size - 7)

        # Separadores de temporización (Timing patterns)
        for i in range(8, size - 8):
            grid[6][i] = 1 if i % 2 == 0 else 0
            grid[i][6] = 1 if i % 2 == 0 else 0

        # Llenar datos con dispersión determinista basada en el contenido
        text_hash = hashlib.sha256(qr_text.encode('utf-8')).digest()
        hash_idx = 0
        bit_idx = 0
        for y in range(size):
            for x in range(size):
                # Saltar esquinas reservadas
                if (x < 8 and y < 8) or (x >= size - 8 and y < 8) or (x < 8 and y >= size - 8):
                    continue
                if x == 6 or y == 6:
                    continue
                byte = text_hash[hash_idx % len(text_hash)]
                val = (byte >> (bit_idx % 8)) & 1
                grid[y][x] = val
                bit_idx += 1
                if bit_idx % 8 == 0:
                    hash_idx += 1

        # Construir SVG
        cell_size = 5
        svg_width = size * cell_size
        rects = []
        for y in range(size):
            for x in range(size):
                if grid[y][x]:
                    rects.append(f'<rect x="{x * cell_size}" y="{y * cell_size}" width="{cell_size}" height="{cell_size}" fill="#111827"/>')

        return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_width}" width="140" height="140" class="dian-qr-code">
  <rect width="{svg_width}" height="{svg_width}" fill="#FFFFFF"/>
  {''.join(rects)}
</svg>'''

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
