"""Auditoría transaccional. Solo los campos normalizables de la lista explícita se escriben."""
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from sqlalchemy import cast, select, String, text
from sqlalchemy.orm import defer, lazyload

from app.extensions import db
from app.models import Category, Order, Product, User
from app.models.billing import Invoice, Payment
from app.models.analytics import QualityIssue, QualityRun
from app.utils.validation import CONTROL_CHARS, clean_text, valid_email


def audit(actor_id):
    if db.session.get_bind().dialect.name == "postgresql":
        # Impide que una edición concurrente se pierda entre la comparación y la corrección.
        db.session.execute(text("LOCK TABLE users, categories, products, orders IN SHARE ROW EXCLUSIVE MODE"))
    issues = []
    counts = {}
    groups = defaultdict(set)
    originals = {}

    def issue(module, entity_id, field, kind, value, proposal=None, *, fixed=False, severity="medium", **extra):
        issues.append(QualityIssue(module=module, entity_id=entity_id, issue_type=kind,
                                   original_value=None if value is None else str(value), normalized_value=proposal,
                                   severity=severity, status="auto_fixed" if fixed else "pending_review",
                                   details={"field": field, **extra}))

    users = User.query.order_by(User.id).all()
    categories = Category.query.order_by(Category.id).all()
    # El cast evita que un precio histórico mal escrito rompa el procesador Numeric de SQLite.
    products = db.session.execute(select(Product.id, cast(Product.price, String).label("raw_price"),
                                         Product.category_id).order_by(Product.id)).all()
    product_objects = Product.query.options(defer(Product.price), lazyload(Product.category)).order_by(Product.id).all()
    orders = Order.query.order_by(Order.id).all()
    for module, objects, fields in (
        ("users", users, ("email",)), ("categories", categories, ("name",)),
        ("products", product_objects, ("name", "sku")),
    ):
        for obj in objects:
            for field in fields:
                value = clean_text(getattr(obj, field) or "").casefold()
                if field == "sku":
                    value = re.sub(r"[\W_]+", "", value)
                if value:
                    groups[module, field, value].add(obj.id)
                    originals[module, field, value, obj.id] = getattr(obj, field)
    customer_ids = {u.id for u in users if u.role == User.ROLE_CUSTOMER}
    for order in orders:
        digits = re.sub(r"\D", "", order.customer_phone or "")
        if digits and order.customer_id in customer_ids:
            groups["users", "phone", digits].add(order.customer_id)
            originals["users", "phone", digits, order.customer_id] = order.customer_phone

    ambiguous = set()
    for (module, field, value), ids in sorted(groups.items()):
        if len(ids) < 2:
            continue
        for entity_id in sorted(ids):
            ambiguous.add((module, entity_id, field))
            issue(module, entity_id, field, "inconsistent_category" if module == "categories" else
                  "duplicate_candidate", originals[module, field, value, entity_id], value, related_entity_ids=sorted(ids - {entity_id}))

    def normalize(module, obj, field, optional=False, multiline=False):
        raw = getattr(obj, field)
        normalized = clean_text(raw or "", multiline=multiline)
        if not normalized:
            if not optional:
                issue(module, obj.id, field, "missing_field", raw, severity="high")
            return
        if field in ("email", "customer_email"):
            normalized = normalized.lower()
            if not valid_email(normalized):
                issue(module, obj.id, field, "malformed_string", raw)
                return
        if module == "products" and field == "sku":
            normalized = normalized.upper()
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,49}", normalized):
                issue(module, obj.id, field, "malformed_string", raw, normalized)
                return
        if module == "categories" and field == "name":
            normalized = normalized.capitalize()
        if raw != normalized:
            safe = (module, obj.id, field) not in ambiguous and not CONTROL_CHARS.search(raw)
            limit = getattr(obj.__table__.c[field].type, "length", None)
            safe = safe and (limit is None or len(normalized) <= limit)
            issue(module, obj.id, field, "malformed_string", raw, normalized, fixed=safe, severity="low")
            if safe:
                setattr(obj, field, normalized)

    counts.update(users=len(users), categories=len(categories), products=len(products), orders=len(orders))
    for user in users:
        normalize("users", user, "email")
        normalize("users", user, "full_name")
    for category in categories:
        normalize("categories", category, "name")
        normalize("categories", category, "headline", optional=True)
    category_ids = {c.id for c in categories}
    for row, product in zip(products, product_objects, strict=True):
        normalize("products", product, "name")
        normalize("products", product, "sku")
        normalize("products", product, "description", optional=True, multiline=True)
        normalize("products", product, "specs", optional=True, multiline=True)
        if row.category_id not in category_ids:
            issue("products", row.id, "category_id", "inconsistent_category", row.category_id, severity="high")
        try:
            value = Decimal(row.raw_price or "")
            valid = value.is_finite() and value > 0
        except InvalidOperation:
            valid = False
        if not valid:
            issue("products", row.id, "price", "invalid_price", row.raw_price, severity="high")

    for order in orders:
        for field in ("customer_name", "customer_email", "customer_phone", "doc_number"):
            normalize("orders", order, field)
    for module, model, amount, required in (
        ("invoices", Invoice, Invoice.total_amount, ("invoice_number", "order_id", "status")),
        ("payments", Payment, Payment.amount, ("invoice_id", "order_id", "payment_method", "status")),
    ):
        rows = db.session.execute(select(model.id, amount, *(getattr(model, k) for k in required))).all()
        counts[module] = len(rows)
        for row in rows:
            for key in required:
                val = getattr(row, key)
                if val is None or (isinstance(val, str) and not val.strip()):
                    issue(module, row.id, key, "missing_field", val, severity="high")
                elif isinstance(val, str) and val != clean_text(val):
                    issue(module, row.id, key, "malformed_string", val, clean_text(val))
            val = getattr(row, amount.key)
            if val is None or val < 0 or (module == "payments" and val == 0):
                issue(module, row.id, amount.key, "invalid_price", val, severity="high")
    total = sum(counts.values())
    summary = {name: {"scanned": count, "auto_fixed": 0, "pending_review": 0} for name, count in counts.items()}
    pending = set()
    for item in issues:
        summary[item.module][item.status] += 1
        if item.status == "pending_review":
            pending.add((item.module, item.entity_id))
    fixed = sum(group["auto_fixed"] for group in summary.values())
    run = QualityRun(executed_by=actor_id, total_records_scanned=total, issues_found=len(issues),
                     auto_fixed_count=fixed, pending_review_count=len(issues)-fixed,
                     quality_score=round(100*(total-len(pending))/total, 2) if total else 100,
                     summary_by_module=summary, issues=issues)
    db.session.add(run)
    db.session.commit()
    return run
