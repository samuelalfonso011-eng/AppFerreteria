from flask import jsonify

from app.api.admin import admin_bp
from app.models import ART_KEYS, DOC_TYPES, MovementType, OrderStatus
from app.services import metrics_service
from app.utils.cache import SCOPE_CATALOG, cache, memo
from app.utils.http import no_store


@admin_bp.get("/dashboard")
def dashboard():
    payload, _, _, hit = memo(SCOPE_CATALOG, "catalog:dashboard", metrics_service.dashboard, ttl=60)
    response = no_store(jsonify(payload))
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return response


@admin_bp.get("/meta")
def meta():
    return no_store(jsonify(
        statuses=[{"code": s, "label": OrderStatus.LABELS[s]} for s in OrderStatus.ALL],
        transitions={k: list(v) for k, v in OrderStatus.TRANSITIONS.items()},
        art_keys=list(ART_KEYS),
        movement_types=[{"code": m, "label": MovementType.LABELS[m]} for m in MovementType.MANUAL],
        doc_types=list(DOC_TYPES),
        cache=cache.stats(),
    ))
