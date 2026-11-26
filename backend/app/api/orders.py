"""Checkout con aceptación legal obligatoria y trazabilidad por canal."""
import re

from flask import abort, jsonify, request

from app.api import api_bp
from app.extensions import db
from app.models import DOC_TYPES, Order, User
from app.models.order import ORDER_CHANNELS
from app.services import order_service
from app.utils.http import json_error, no_store
from app.utils.security import client_ip, current_user, limiter
from app.utils.validation import ValidationError, Validator

PHONE_RE = re.compile(r"^\+?[0-9 ]{7,20}$")
DOC_RE = re.compile(r"^[0-9A-Za-z.-]{4,20}$")
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")
ORDER_NUMBER_RE = re.compile(r"^FP-\d{6}-[0-9A-F]{6}$")
MAX_LINES = 50
MAX_QTY = 99


def _parse_items(raw, validator):
    if not isinstance(raw, list) or not raw:
        validator.error("items", "Tu carrito está vacío.")
        return {}
    if len(raw) > MAX_LINES:
        validator.error("items", "El carrito tiene demasiados productos.")
        return {}
    items = {}
    for line in raw:
        if not isinstance(line, dict):
            validator.error("items", "El carrito no es válido.")
            return {}
        pid, qty = line.get("product_id"), line.get("quantity")
        if (not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0
                or not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0):
            validator.error("items", "El carrito no es válido.")
            return {}
        items[pid] = items.get(pid, 0) + qty
        if items[pid] > MAX_QTY:
            validator.error("items", f"Puedes pedir hasta {MAX_QTY} unidades por producto.")
            return {}
    return items


@api_bp.post("/orders")
def create_order():
    allowed, retry = limiter("checkout").hit(client_ip())
    if not allowed:
        return json_error(429, "rate_limited", "Hiciste muchos pedidos seguidos. Intenta de nuevo en unos minutos.",
                          retry_after=retry)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"order": "Envía un objeto JSON con los datos del pedido."})
    v = Validator(data)
    channel = v.choice("channel", ORDER_CHANNELS, required=False, default="web")
    delivery_address = channel != "presencial"
    customer = {
        "customer_name": v.text("name", 150, min_len=3),
        "customer_email": v.email("email"),
        "customer_phone": v.text("phone", 20, min_len=7, pattern=PHONE_RE,
                                 pattern_msg="Escribe un celular válido, solo números."),
        "doc_type": v.choice("doc_type", DOC_TYPES),
        "doc_number": v.text("doc_number", 20, min_len=4, pattern=DOC_RE,
                             pattern_msg="Escribe el número sin espacios."),
        "department": v.text("department", 100, min_len=3, required=delivery_address) or "",
        "city": v.text("city", 100, min_len=3, required=delivery_address) or "",
        "neighborhood": v.text("neighborhood", 100, min_len=2, required=delivery_address) or "",
        "street_address": v.text("street_address", 255, min_len=5, required=delivery_address) or "",
        "complement": v.text("complement", 100, required=False),
        "notes": v.text("notes", 500, required=False, multiline=True),
    }
    v.accepted("accept_terms", "Para continuar debes aceptar los Términos y la Política de devoluciones.")
    v.accepted("accept_privacy", "Para continuar debes autorizar el tratamiento de tus datos personales.")
    items = _parse_items(data.get("items"), v)

    key = data.get("idempotency_key")
    if not isinstance(key, str) or not IDEMPOTENCY_RE.fullmatch(key):
        v.error("idempotency_key", "Recarga la página e inténtalo de nuevo.")
    expected_total = v.integer("expected_total", 0, 10_000_000_000, required=False)
    user = current_user()
    staff = user is not None and user.is_staff
    customer_id = user.id if user and not staff else None
    if "customer_id" in v.data:
        if not staff:
            abort(403)
        customer_id = v.integer("customer_id", 1, 2_147_483_647, required=False)
        if customer_id is not None:
            account = db.session.get(User, customer_id)
            if account is None or account.role != User.ROLE_CUSTOMER or not account.is_active:
                v.error("customer_id", "Elige un cliente activo.")
    v.raise_if_errors()
    if channel in ("presencial", "domicilio") and not staff:
        abort(403)
    order, created = order_service.create_order(
        customer, items, key, expected_total, request.remote_addr,
        channel=channel, customer_id=customer_id, employee_id=user.id if staff else None,
    )
    details = order.admin_detail() if staff else order.public_view()
    return no_store(jsonify(order=details, created=created), 201 if created else 200)


@api_bp.post("/orders/lookup")
def lookup_order():
    """Consulta de estado con numero de pedido y correo (POST para no exponer el correo en la URL)."""
    allowed, retry = limiter("lookup").hit(client_ip())
    if not allowed:
        return json_error(429, "rate_limited", "Demasiadas consultas. Intenta de nuevo en unos minutos.",
                          retry_after=retry)
    data = request.get_json(silent=True) or {}
    v = Validator(data)
    number = (v.text("order_number", 20) or "").upper()
    email = v.email("email")
    if number and "order_number" not in v.errors and not ORDER_NUMBER_RE.fullmatch(number):
        v.error("order_number", "El número tiene el formato FP-000000-XXXXXX.")
    v.raise_if_errors()
    order = Order.query.filter_by(order_number=number).first()
    if order is None or order.customer_email != email:
        return json_error(404, "not_found", "No encontramos un pedido con esos datos.")
    return no_store(jsonify(order=order.public_view()))
