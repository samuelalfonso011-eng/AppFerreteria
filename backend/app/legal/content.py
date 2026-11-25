"""Textos legales de la tienda (Colombia), versionados.

Plantilla base: el responsable debe completar razon social, NIT y datos de contacto en
Admin > Ajustes y hacerla revisar por un abogado antes de operar con datos reales.
Al cambiar el fondo de cualquier texto, sube POLICY_VERSION: los pedidos guardan la version
que el cliente acepto.
"""

POLICY_VERSION = "2026-11-21"
UPDATED_LABEL = "21 de noviembre de 2026"

DOCUMENTS = {
    "privacidad": {
        "title": "Política de privacidad",
        "kicker": "Protección de datos",
        "law": "Ley 1581 de 2012",
        "sections": [
            {"heading": "Quién es responsable de tus datos",
             "paragraphs": [
                 "{legal_name} ({store_name}), {nit_text}, con domicilio en {address}, teléfono {phone} y correo {email}, es responsable del tratamiento de los datos personales que entregas en esta tienda, conforme a la Ley 1581 de 2012, el Decreto 1074 de 2015 y las demás normas que los modifiquen.",
             ]},
            {"heading": "Qué datos recogemos",
             "items": [
                 "Identificación y contacto: nombre, correo electrónico, celular y documento de identidad.",
                 "Entrega: departamento, ciudad, barrio, dirección y notas de entrega.",
                 "Compra: productos, valores, estado del pedido y la fecha y hora en que aceptaste estas políticas.",
                 "Preferencias técnicas en tu navegador: carrito y tema visual. No usamos analítica ni publicidad.",
             ],
             "paragraphs": ["No pedimos datos sensibles ni datos de niñas, niños o adolescentes."]},
            {"heading": "Para qué los usamos",
             "items": [
                 "Procesar, confirmar, preparar y entregar tu pedido.",
                 "Emitir la factura electrónica de venta y cumplir obligaciones contables y tributarias.",
                 "Atender garantías, devoluciones, consultas y reclamos.",
                 "Proteger la tienda y a los clientes frente a fraude y accesos no autorizados.",
             ],
             "paragraphs": ["No vendemos tus datos ni los usamos para publicidad. Si algún día quisiéramos enviarte promociones, te pediremos una autorización separada y opcional."]},
            {"heading": "Tus derechos",
             "paragraphs": [
                 "Puedes conocer, actualizar, rectificar y suprimir tus datos, pedir prueba de la autorización, saber cómo los usamos y revocar la autorización cuando no exista un deber legal o contractual de conservarlos. El procedimiento y los plazos están en la Política de tratamiento de datos.",
             ]},
            {"heading": "Seguridad y conservación",
             "paragraphs": [
                 "Aplicamos controles técnicos y administrativos: conexión cifrada, contraseñas del personal guardadas con hash, sesiones protegidas y acceso administrativo restringido por rol. Conservamos los datos del pedido mientras dure la relación comercial y durante el tiempo que exijan las normas contables y tributarias.",
             ]},
        ],
        "related": ["datos", "cookies"],
    },
    "datos": {
        "title": "Política de tratamiento de datos personales",
        "kicker": "Habeas Data",
        "law": "Ley 1581 de 2012 y Decreto 1074 de 2015",
        "sections": [
            {"heading": "Autorización",
             "paragraphs": [
                 "Antes de registrar tu pedido te pedimos una autorización previa, expresa e informada, mediante una casilla que no viene marcada. Guardamos como prueba la finalidad, la versión de esta política y la fecha y hora de aceptación.",
                 "Sin esta autorización no podemos procesar el pedido, porque los datos son necesarios para entregarlo y facturarlo.",
             ]},
            {"heading": "Derechos del titular",
             "items": [
                 "Conocer, actualizar y rectificar tus datos.",
                 "Solicitar prueba de la autorización otorgada.",
                 "Ser informado sobre el uso que se ha dado a tus datos.",
                 "Revocar la autorización o pedir la supresión cuando no exista un deber legal o contractual de conservarlos.",
                 "Acceder gratuitamente a tus datos.",
                 "Presentar quejas ante la Superintendencia de Industria y Comercio después de agotar el trámite con nosotros.",
             ]},
            {"heading": "Cómo presentar una consulta o un reclamo",
             "paragraphs": [
                 "Escribe a {email} con tu nombre, documento, un medio para responderte y la descripción de tu solicitud. Podemos pedirte información adicional y proporcional para verificar tu identidad. Nunca te pediremos tu contraseña.",
                 "Las consultas se responden en un máximo de diez (10) días hábiles, prorrogables por cinco (5) días hábiles más con aviso motivado. Los reclamos se resuelven en un máximo de quince (15) días hábiles, prorrogables por ocho (8) días hábiles más con aviso motivado. Si el reclamo está incompleto, te pediremos completarlo dentro de los cinco (5) días siguientes.",
             ]},
            {"heading": "Encargados y transferencias",
             "paragraphs": [
                 "Los proveedores de alojamiento, base de datos y transporte pueden tratar datos por nuestra cuenta como encargados, bajo contrato y solo para las finalidades descritas. Si alguno se ubica fuera de Colombia, verificaremos que cumpla niveles adecuados de protección según la ley.",
             ]},
            {"heading": "Vigencia",
             "paragraphs": [
                 "Esta política rige desde el {updated}. Cualquier cambio sustancial se publicará en esta página y, cuando la ley lo exija, pediremos una nueva autorización.",
             ]},
        ],
        "related": ["privacidad"],
    },
    "terminos": {
        "title": "Términos y condiciones",
        "kicker": "Condiciones de compra",
        "law": "Ley 1480 de 2011 y Ley 527 de 1999",
        "sections": [
            {"heading": "Aplicación",
             "paragraphs": [
                 "Estos términos regulan las compras en {store_name}, operada por {legal_name}, {nit_text}. Al confirmar un pedido declaras que los leíste y los aceptas. Aplican el Estatuto del Consumidor (Ley 1480 de 2011) y las normas de comercio electrónico (Ley 527 de 1999).",
             ]},
            {"heading": "Precios y disponibilidad",
             "paragraphs": [
                 "Los precios están en pesos colombianos e incluyen los impuestos aplicables. El valor que vale es el que calcula nuestro servidor al confirmar el pedido: si un precio cambió mientras comprabas, te lo mostraremos antes de registrar la compra. El stock se valida y se reserva en el momento de confirmar.",
             ]},
            {"heading": "Pedido, pago y confirmación",
             "paragraphs": [
                 "Al confirmar recibes un número de pedido. Te contactaremos al celular registrado para coordinar el pago y la entrega. El pedido queda en firme cuando lo confirmamos; si no se confirma en el plazo informado, se cancela y el stock vuelve a estar disponible.",
             ]},
            {"heading": "Envíos",
             "paragraphs": [
                 "El costo de envío se muestra antes de confirmar. Las compras desde {free_shipping} tienen envío sin costo. Los materiales largos o pesados, como tubería, láminas o cable en rollo, pueden requerir coordinación especial.",
             ]},
            {"heading": "Facturación electrónica",
             "paragraphs": [
                 "Emitimos factura electrónica de venta conforme a la regulación de la DIAN con los datos de documento y nombre que entregues en el pedido. Revisa que sean correctos: una factura emitida solo puede corregirse mediante nota crédito.",
             ]},
            {"heading": "Cancelaciones, retracto y garantías",
             "paragraphs": [
                 "Puedes pedir la cancelación mientras el pedido no haya salido a preparación. El derecho de retracto, la reversión del pago y la garantía legal se explican en la Política de devoluciones y garantías.",
             ]},
            {"heading": "Ley aplicable",
             "paragraphs": [
                 "Estos términos se rigen por las leyes de Colombia. Conservas siempre las acciones de protección al consumidor ante la Superintendencia de Industria y Comercio.",
             ]},
        ],
        "related": ["devoluciones", "privacidad"],
    },
    "devoluciones": {
        "title": "Devoluciones, retracto y garantías",
        "kicker": "Protección al consumidor",
        "law": "Ley 1480 de 2011 y Decreto 1074 de 2015",
        "sections": [
            {"heading": "Derecho de retracto",
             "paragraphs": [
                 "En compras a distancia puedes retractarte dentro de los cinco (5) días hábiles siguientes a la entrega, sin justificar tu decisión (artículo 47 de la Ley 1480 de 2011). El producto debe estar sin uso, completo y en su empaque. Los costos de transporte de la devolución corren por tu cuenta. Devolvemos el dinero dentro de los treinta (30) días calendario siguientes.",
             ]},
            {"heading": "Cuándo no aplica el retracto",
             "items": [
                 "Bienes hechos según tus especificaciones o claramente personalizados, como tubería, cable o lámina cortados a la medida que pediste.",
                 "Bienes que por su naturaleza no puedan devolverse o se deterioren con rapidez.",
                 "Las demás excepciones previstas en la ley.",
             ]},
            {"heading": "Reversión del pago",
             "paragraphs": [
                 "Si pagaste con un medio electrónico y hubo fraude, una operación no solicitada, o el producto no llegó, no corresponde a lo pedido o es defectuoso, puedes pedir la reversión del pago dentro de los cinco (5) días hábiles siguientes a que conozcas la situación (artículo 51 de la Ley 1480 de 2011). Avísanos a {email} y a tu entidad financiera.",
             ]},
            {"heading": "Garantía legal",
             "paragraphs": [
                 "Todos los productos tienen garantía legal de calidad, idoneidad y seguridad. Si el fabricante no indica otro término, la garantía es de un (1) año para productos nuevos. Ante un defecto puedes pedir la reparación gratuita; si el defecto se repite o no es posible repararlo, el cambio del producto o la devolución del dinero.",
             ]},
            {"heading": "Cómo hacer una solicitud",
             "items": [
                 "Escribe a {email} con tu número de pedido y una descripción del caso. Si puedes, adjunta fotos.",
                 "Te respondemos con el procedimiento y la dirección de devolución.",
                 "Al recibir y revisar el producto, hacemos la reparación, el cambio o el reembolso por el mismo medio de pago.",
             ]},
        ],
        "related": ["terminos"],
    },
    "cookies": {
        "title": "Cookies y almacenamiento local",
        "kicker": "Tu navegador",
        "law": "Ley 1581 de 2012",
        "sections": [
            {"heading": "Qué guardamos",
             "paragraphs": ["Solo usamos almacenamiento propio y necesario para que la tienda funcione. No instalamos analítica, píxeles de seguimiento ni publicidad de terceros."],
             "items": [
                 "ferrepro_session (cookie): sesión firmada con el token de seguridad de tus pedidos y, para el personal, el inicio de sesión. No contiene contraseñas. Se borra al cerrar el navegador; la sesión del personal vence a las ocho horas.",
                 "ferrepro.cart.v2 (almacenamiento local): los productos y cantidades de tu carrito. Se borra al confirmar el pedido.",
                 "ferrepro.theme (almacenamiento local): tu elección de modo claro u oscuro.",
                 "ferrepro.notice (almacenamiento local): que ya viste el aviso de privacidad.",
             ]},
            {"heading": "Cómo controlarlo",
             "paragraphs": [
                 "Puedes borrar estos datos desde la configuración de tu navegador cuando quieras. Si bloqueas la cookie de sesión no podrás confirmar pedidos, porque protege el formulario contra envíos falsificados.",
             ]},
        ],
        "related": ["privacidad"],
    },
}

ORDER = ("privacidad", "datos", "terminos", "devoluciones", "cookies")


def _format_money(value):
    if not value:
        return "el valor indicado en la tienda"
    return "$ " + f"{int(value):,}".replace(",", ".")


def _context(store):
    nit = (store.get("nit") or "").strip()
    return {
        "store_name": store.get("store_name") or "FerrePro",
        "legal_name": store.get("legal_name") or "FerrePro S.A.S.",
        "nit_text": f"NIT {nit}" if nit else "NIT pendiente de registrar",
        "address": store.get("address") or "",
        "phone": store.get("phone") or "",
        "email": store.get("email") or "",
        "free_shipping": _format_money(store.get("free_shipping_threshold")),
        "updated": UPDATED_LABEL,
    }


def render_document(slug, store):
    doc = DOCUMENTS.get(slug)
    if doc is None:
        return None
    ctx = _context(store)
    sections = []
    for section in doc["sections"]:
        sections.append({
            "heading": section["heading"],
            "paragraphs": [p.format_map(ctx) for p in section.get("paragraphs", [])],
            "items": [i.format_map(ctx) for i in section.get("items", [])],
        })
    return {
        "slug": slug,
        "title": doc["title"],
        "kicker": doc["kicker"],
        "law": doc["law"],
        "version": POLICY_VERSION,
        "updated": UPDATED_LABEL,
        "sections": sections,
        "related": [{"slug": r, "title": DOCUMENTS[r]["title"]} for r in doc["related"]],
    }


def document_index():
    return [{"slug": s, "title": DOCUMENTS[s]["title"]} for s in ORDER]
