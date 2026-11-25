"""Clientes registrados: solo lectura, solo administradores (el guardia vive en admin_bp).

La respuesta se construye campo por campo desde una lista blanca: nunca incluye
password_hash, tokens, sesiones ni direcciones IP. Las pruebas lo comprueban.
"""
from flask import jsonify, request
from sqlalchemy import func, or_

from app.api.admin import admin_bp
from app.extensions import db
from app.models import Order, PrivacyConsent, User
from app.utils.http import no_store
from app.utils.timeutils import iso

PER_PAGE = 25
FILTERS = ("all", "verified", "pending")


def _status(user):
    if user.email_verification_pending:
        return "pending"
    return "verified" if user.is_active else "disabled"


def _like(term):
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@admin_bp.get("/customers")
def list_customers():
    query = User.query.filter(User.role == User.ROLE_CUSTOMER)

    term = request.args.get("q", "").strip()[:100]
    if term:
        like = _like(term)
        query = query.filter(or_(User.full_name.ilike(like, escape="\\"), User.email.ilike(like, escape="\\")))

    status = request.args.get("status", "all")
    if status not in FILTERS:
        status = "all"
    if status == "verified":
        query = query.filter(User.is_active.is_(True), User.email_verification_pending.is_(False))
    elif status == "pending":
        query = query.filter(User.email_verification_pending.is_(True))

    try:
        page = max(1, min(int(request.args.get("page", 1)), 10_000))
    except ValueError:
        page = 1
    total = query.count()
    users = (query.order_by(User.created_at.desc(), User.id.desc())
             .offset((page - 1) * PER_PAGE).limit(PER_PAGE).all())

    ids = [u.id for u in users]
    emails = [u.email.strip().lower() for u in users]

    # Pedidos por correo (la tabla de pedidos no guarda user_id): una sola consulta agrupada
    orders = {}
    if emails:
        orders = dict(db.session.query(func.lower(Order.customer_email), func.count(Order.id))
                      .filter(func.lower(Order.customer_email).in_(emails))
                      .group_by(func.lower(Order.customer_email)).all())

    # Ultima aceptacion de Habeas Data por usuario
    consents = {}
    if ids:
        rows = (db.session.query(PrivacyConsent.user_id, PrivacyConsent.accepted_at, PrivacyConsent.policy_version)
                .filter(PrivacyConsent.user_id.in_(ids), PrivacyConsent.document == "habeas_data")
                .order_by(PrivacyConsent.accepted_at.asc()).all())
        for user_id, accepted_at, version in rows:
            consents[user_id] = (accepted_at, version)

    # Conteos para los filtros rapidos (independientes de la busqueda y la pagina)
    base = db.session.query(User).filter(User.role == User.ROLE_CUSTOMER)
    counts = {
        "all": base.count(),
        "verified": base.filter(User.is_active.is_(True), User.email_verification_pending.is_(False)).count(),
        "pending": base.filter(User.email_verification_pending.is_(True)).count(),
    }

    customers = []
    for user in users:
        accepted = consents.get(user.id)
        customers.append({
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "status": _status(user),
            "created_at": iso(user.created_at),
            "last_login_at": iso(user.last_login_at),
            "orders": orders.get(user.email.strip().lower(), 0),
            "habeas_data": {"accepted": accepted is not None,
                            "accepted_at": iso(accepted[0]) if accepted else None,
                            "policy_version": accepted[1] if accepted else None},
        })

    return no_store(jsonify(customers=customers, page=page, pages=max(1, -(-total // PER_PAGE)),
                            total=total, counts=counts, status=status))
