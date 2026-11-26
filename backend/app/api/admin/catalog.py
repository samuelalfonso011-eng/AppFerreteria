"""CRUD de productos y categorias. Cada commit cambia el token de cache del catalogo."""
import re
from decimal import Decimal

from flask import abort, jsonify, request
from sqlalchemy import func, or_

from app.api.admin import admin_bp
from app.extensions import db
from app.models import ART_KEYS, Category, MovementType, OrderItem, Product
from app.services import inventory_service
from app.utils.http import json_error, no_store
from app.utils.security import current_user
from app.utils.validation import Validator, slugify

SKU_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,49}$")


def _unique_slug(model, base, exclude_id=None):
    slug, n = base, 2
    while True:
        query = model.query.filter(model.slug == slug)
        if exclude_id is not None:
            query = query.filter(model.id != exclude_id)
        if query.first() is None:
            return slug
        slug = f"{base[:200]}-{n}"
        n += 1


def _like(term):
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# ---------------------------------------------------------------------------
# Productos
# ---------------------------------------------------------------------------

@admin_bp.get("/products")
def list_products():
    query = Product.query
    term = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "all")
    if term:
        like = _like(term)
        query = query.filter(or_(Product.name.ilike(like, escape="\\"), Product.sku.ilike(like, escape="\\")))
    if status == "active":
        query = query.filter(Product.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(Product.is_active.is_(False))
    elif status == "low":
        query = query.filter(Product.stock <= Product.min_stock_alert)
    rows = query.order_by(Product.name.asc()).all()
    return no_store(jsonify(products=[p.to_admin() for p in rows]))


def _product_fields(data, product=None):
    v = Validator(data)
    fields = {
        "name": v.text("name", 200, min_len=3),
        "sku": (v.text("sku", 50, min_len=2) or "").upper(),
        "category_id": v.integer("category_id", 1, 2_000_000_000),
        "price": v.money("price", Decimal("0.01"), 1_000_000_000),
        "min_stock_alert": v.integer("min_stock_alert", 0, 100_000, required=False, default=5),
        "art": v.choice("art", ART_KEYS, default="wrench"),
        "description": v.text("description", 2000, required=False, multiline=True),
        "specs": v.text("specs_text", 2000, required=False, multiline=True),
        "is_active": v.boolean("is_active", default=True),
    }
    initial_stock = 0
    if product is None:
        initial_stock = v.integer("initial_stock", 0, 100_000, required=False, default=0)

    if fields["sku"] and "sku" not in v.errors:
        if not SKU_RE.fullmatch(fields["sku"]):
            v.error("sku", "Usa letras, números y guiones, por ejemplo FP-0007.")
        else:
            clash = Product.query.filter(Product.sku == fields["sku"])
            if product is not None:
                clash = clash.filter(Product.id != product.id)
            if clash.first():
                v.error("sku", "Ya existe un producto con este SKU.")
    if fields["category_id"] and "category_id" not in v.errors and db.session.get(Category, fields["category_id"]) is None:
        v.error("category_id", "Elige una categoría existente.")
    v.raise_if_errors()
    return fields, initial_stock


@admin_bp.post("/products")
def create_product():
    fields, initial_stock = _product_fields(request.get_json(silent=True))
    product = Product(slug=_unique_slug(Product, slugify(fields["name"])), stock=0, **fields)
    try:
        db.session.add(product)
        db.session.flush()
        if initial_stock:
            inventory_service.increase(product, initial_stock, MovementType.PURCHASE_ENTRY,
                                       "Inventario inicial", user_id=current_user().id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return no_store(jsonify(product=db.session.get(Product, product.id).to_admin()), 201)


@admin_bp.put("/products/<int:product_id>")
def update_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    fields, _ = _product_fields(request.get_json(silent=True), product)
    if fields["name"] != product.name:
        product.slug = _unique_slug(Product, slugify(fields["name"]), exclude_id=product.id)
    for key, value in fields.items():
        setattr(product, key, value)
    db.session.commit()
    return no_store(jsonify(product=product.to_admin()))


@admin_bp.post("/products/<int:product_id>/toggle")
def toggle_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    product.is_active = not product.is_active
    db.session.commit()
    return no_store(jsonify(product=product.to_admin()))


@admin_bp.delete("/products/<int:product_id>")
def delete_product(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if OrderItem.query.filter_by(product_id=product.id).first():
        return json_error(409, "in_orders",
                          "Este producto aparece en pedidos. Desactívalo para ocultarlo de la tienda sin perder el historial.")
    db.session.delete(product)
    db.session.commit()
    return no_store(jsonify(ok=True))


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------

@admin_bp.get("/categories")
def list_categories():
    counts = dict(db.session.query(Product.category_id, func.count(Product.id)).group_by(Product.category_id).all())
    rows = Category.query.order_by(Category.sort_order.asc(), Category.name.asc()).all()
    return no_store(jsonify(categories=[c.to_admin(counts.get(c.id, 0)) for c in rows]))


def _category_fields(data, category=None):
    v = Validator(data)
    fields = {
        "name": v.text("name", 80, min_len=2),
        "headline": v.text("headline", 120, required=False),
        "art": v.choice("art", ART_KEYS, default="wrench"),
        "sort_order": v.integer("sort_order", 0, 999, required=False, default=0),
        "is_active": v.boolean("is_active", default=True),
    }
    if fields["name"] and "name" not in v.errors:
        fields["name"] = fields["name"].capitalize()
        clash = Category.query.filter(func.lower(Category.name) == fields["name"].lower())
        if category is not None:
            clash = clash.filter(Category.id != category.id)
        if clash.first():
            v.error("name", "Ya existe una categoría con este nombre.")
    v.raise_if_errors()
    return fields


@admin_bp.post("/categories")
def create_category():
    fields = _category_fields(request.get_json(silent=True))
    category = Category(slug=_unique_slug(Category, slugify(fields["name"], 100)), **fields)
    db.session.add(category)
    db.session.commit()
    return no_store(jsonify(category=category.to_admin()), 201)


@admin_bp.put("/categories/<int:category_id>")
def update_category(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    fields = _category_fields(request.get_json(silent=True), category)
    if fields["name"] != category.name:
        category.slug = _unique_slug(Category, slugify(fields["name"], 100), exclude_id=category.id)
    for key, value in fields.items():
        setattr(category, key, value)
    db.session.commit()
    return no_store(jsonify(category=category.to_admin()))


@admin_bp.post("/categories/<int:category_id>/toggle")
def toggle_category(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    category.is_active = not category.is_active
    db.session.commit()
    return no_store(jsonify(category=category.to_admin()))
