from flask import abort, jsonify, request

from app.api.admin import admin_bp
from app.extensions import db
from app.models import InventoryMovement, MovementType, Product
from app.services import inventory_service
from app.utils.http import no_store
from app.utils.security import current_user
from app.utils.validation import Validator


@admin_bp.get("/inventory")
def inventory_overview():
    rows = Product.query.order_by(Product.name.asc()).all()
    rows.sort(key=lambda p: (not p.is_low_stock, p.name.lower()))
    return no_store(jsonify(products=[{
        "id": p.id, "name": p.name, "sku": p.sku, "stock": p.stock,
        "min_stock_alert": p.min_stock_alert, "is_low_stock": p.is_low_stock, "is_active": p.is_active,
        "category": p.category.name if p.category else None,
    } for p in rows]))


@admin_bp.get("/inventory/<int:product_id>/movements")
def inventory_movements(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    rows = (InventoryMovement.query.filter_by(product_id=product.id)
            .order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc()).limit(100).all())
    return no_store(jsonify(product={"id": product.id, "name": product.name, "sku": product.sku,
                                     "stock": product.stock},
                            movements=[m.to_dict() for m in rows]))


@admin_bp.post("/inventory/<int:product_id>/adjust")
def inventory_adjust(product_id):
    v = Validator(request.get_json(silent=True))
    movement_type = v.choice("movement_type", MovementType.MANUAL)
    quantity = v.integer("quantity", 1, 100_000)
    reason = v.text("reason", 255, min_len=5)
    v.raise_if_errors()
    product = inventory_service.manual_adjustment(product_id, movement_type, quantity, reason, current_user().id)
    return no_store(jsonify(product=product.to_admin()))
