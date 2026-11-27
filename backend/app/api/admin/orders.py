from flask import abort, jsonify, request
from sqlalchemy import or_

from app.api import api_bp
from app.api.admin import admin_bp
from app.extensions import db
from app.models import Order, OrderStatus, PrivacyConsent, User
from app.models.order import ORDER_CHANNELS
from app.services import order_service
from app.utils.http import no_store
from app.utils.security import current_user, require_staff
from app.utils.validation import ValidationError, Validator

PER_PAGE = 25


@admin_bp.get("/orders")
def list_orders():
    order_service.maybe_expire_stale_orders()
    return _orders_page(Order.query)


@api_bp.get("/staff/orders")
def staff_orders():
    require_staff()
    return _orders_page(Order.query)


@api_bp.get("/staff/orders/<int:order_id>")
def staff_order_detail(order_id):
    require_staff()
    order = db.session.get(Order, order_id) or abort(404)
    return no_store(jsonify(order=dict(order.public_view(), customer_name=order.customer_name)))


def _orders_page(query):
    channel = request.args.get("channel")
    if channel is not None and channel not in ORDER_CHANNELS:
        raise ValidationError({"channel": "Elige un canal válido."})

    if channel is not None:
        query = query.filter(Order.channel == channel)
    status = request.args.get("status", "")
    if status in OrderStatus.ALL:
        query = query.filter(Order.status == status)
    term = request.args.get("q", "").strip()[:100]
    if term:
        like = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter(or_(Order.order_number.ilike(like, escape="\\"),
                                 Order.customer_name.ilike(like, escape="\\"),
                                 Order.customer_email.ilike(like, escape="\\")))
    try:
        page = max(1, min(int(request.args.get("page", 1)), 10_000))
    except ValueError:
        page = 1
    total = query.count()
    rows = (query.order_by(Order.created_at.desc(), Order.id.desc())
            .offset((page - 1) * PER_PAGE).limit(PER_PAGE).all())
    staff_ids = {order.employee_id for order in rows if order.employee_id is not None}
    names = dict(db.session.query(User.id, User.full_name).filter(User.id.in_(staff_ids)).all()) if staff_ids else {}
    return no_store(jsonify(orders=[dict(o.summary(), employee_name=names.get(o.employee_id)) for o in rows], page=page,
                            pages=max(1, -(-total // PER_PAGE)), total=total))


@admin_bp.get("/orders/<int:order_id>")
def order_detail(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    data = order.admin_detail()
    data["consents"] = [c.to_dict() for c in PrivacyConsent.query.filter_by(order_id=order.id)
                        .order_by(PrivacyConsent.id).all()]
    return no_store(jsonify(order=data))


@admin_bp.post("/orders/<int:order_id>/status")
def order_change_status(order_id):
    v = Validator(request.get_json(silent=True))
    new_status = v.choice("status", OrderStatus.ALL)
    comment = v.text("comment", 500, required=False, multiline=True)
    v.raise_if_errors()
    order = order_service.change_status(order_id, new_status, current_user().id, comment)
    return no_store(jsonify(order=order.admin_detail()))
