"""Lecturas publicas de alta frecuencia: catalogo, categorias, tienda y textos legales."""
from flask import abort, request

from app.api import api_bp
from app.legal.content import document_index, render_document
from app.models import Category, Product, StoreSetting
from app.utils.cache import SCOPE_CATALOG, SCOPE_STORE, cached_json_response
from app.utils.validation import SLUG_RE


def _active_products():
    return (Product.query.join(Category, Product.category_id == Category.id)
            .filter(Product.is_active.is_(True), Category.is_active.is_(True)))


def build_categories():
    rows = (Category.query.filter_by(is_active=True)
            .order_by(Category.sort_order.asc(), Category.name.asc()).all())
    return {"categories": [c.to_public() for c in rows]}


@api_bp.get("/catalog/categories")
def catalog_categories():
    return cached_json_response(SCOPE_CATALOG, "catalog:categories", build_categories)


def build_products(category=""):
    query = _active_products()
    if category:
        query = query.filter(Category.slug == category)
    rows = query.order_by(Product.created_at.asc(), Product.id.asc()).all()
    return {"products": [p.to_public() for p in rows]}


@api_bp.get("/catalog/products")
def catalog_products():
    category = request.args.get("category", "").strip()
    if category and (len(category) > 100 or not SLUG_RE.fullmatch(category)):
        abort(400)

    return cached_json_response(SCOPE_CATALOG, f"catalog:products:{category or 'all'}",
                                lambda: build_products(category))


@api_bp.get("/catalog/products/<slug>")
def catalog_product(slug):
    if len(slug) > 220 or not SLUG_RE.fullmatch(slug):
        abort(404)

    def build():
        product = _active_products().filter(Product.slug == slug).first()
        if product is None:
            abort(404)  # No se cachea: la excepcion sale antes de guardar
        return {"product": product.to_public()}
    return cached_json_response(SCOPE_CATALOG, f"catalog:product:{slug}", build)


def build_store():
    return {"store": StoreSetting.get().to_public()}


@api_bp.get("/store")
def store_info():
    return cached_json_response(SCOPE_STORE, "store:public", build_store)


@api_bp.get("/legal")
def legal_index():
    return cached_json_response(SCOPE_STORE, "store:legal:index", lambda: {"documents": document_index()})


@api_bp.get("/legal/<slug>")
def legal_document(slug):
    if len(slug) > 30 or not SLUG_RE.fullmatch(slug):
        abort(404)

    def build():
        document = render_document(slug, StoreSetting.get().to_public())
        if document is None:
            abort(404)
        return {"document": document}
    return cached_json_response(SCOPE_STORE, f"store:legal:{slug}", build)
