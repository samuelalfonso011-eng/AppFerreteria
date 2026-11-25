import re

from flask import jsonify, request

from app.api.admin import admin_bp
from app.extensions import db
from app.models import StoreSetting
from app.utils.http import no_store
from app.utils.validation import Validator

NIT_RE = re.compile(r"^[0-9.]{5,15}(-[0-9])?$")
PHONE_RE = re.compile(r"^\+?[0-9 ]{7,20}$")


@admin_bp.get("/settings")
def get_settings():
    return no_store(jsonify(settings=StoreSetting.get().to_public()))


@admin_bp.put("/settings")
def update_settings():
    v = Validator(request.get_json(silent=True))
    fields = {
        "store_name": v.text("store_name", 150, min_len=2),
        "legal_name": v.text("legal_name", 150, min_len=2),
        "nit": v.text("nit", 30, required=False, pattern=NIT_RE,
                      pattern_msg="Escribe el NIT con dígito de verificación, por ejemplo 900123456-7.") or "",
        "address": v.text("address", 255, min_len=5),
        "phone": v.text("phone", 50, min_len=7, pattern=PHONE_RE, pattern_msg="Escribe solo números."),
        "email": v.email("email"),
        "business_hours": v.text("business_hours", 255, min_len=5),
        "shipping_cost": v.money("shipping_cost", 0, 10_000_000),
        "free_shipping_threshold": v.money("free_shipping_threshold", 0, 1_000_000_000, required=False),
    }
    v.raise_if_errors()
    setting = StoreSetting.query.order_by(StoreSetting.id).first()
    if setting is None:
        setting = StoreSetting()
        db.session.add(setting)
    for key, value in fields.items():
        setattr(setting, key, value)
    db.session.commit()
    return no_store(jsonify(settings=setting.to_public()))
