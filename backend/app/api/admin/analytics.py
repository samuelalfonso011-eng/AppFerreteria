from flask import abort, jsonify, request

from app.api.admin import admin_bp
from app.extensions import db
from app.models import Product
from app.models.analytics import QualityRun
from app.services import data_quality_service, statistics_service
from app.utils.security import current_user
from app.utils.validation import Validator


@admin_bp.post("/data-quality/audit")
def audit_quality():
    return jsonify(data_quality_service.audit(current_user().id).report())


@admin_bp.get("/data-quality/latest")
def latest_quality():
    latest = QualityRun.query.order_by(QualityRun.id.desc()).first()
    return jsonify(latest.report() if latest else None)


@admin_bp.get("/analytics/users")
def analytics_users():
    return jsonify(statistics_service.user_analytics())


@admin_bp.get("/analytics/demand")
def analytics_demand():
    v = Validator(request.args.to_dict())
    period = v.choice("period", ("daily", "weekly"), required=False, default="daily")
    horizon = v.integer("horizon", 1, 30, required=False, default=3)
    pid = v.integer("product_id", 1, 2_147_483_647, required=False)
    v.raise_if_errors()
    if pid is not None and db.session.get(Product, pid) is None:
        abort(404)
    return jsonify(statistics_service.demand(period, horizon, pid))
