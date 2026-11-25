from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models import Order, OrderItem, OrderStatus, Product
from app.utils.timeutils import BOGOTA, as_utc, bogota_date, bogota_midnight, money, utcnow


def _sales_since(start):
    value = (db.session.query(func.coalesce(func.sum(Order.total), 0))
             .filter(Order.status.in_(OrderStatus.SALES), Order.created_at >= start).scalar())
    return Decimal(value or 0)


def dashboard():
    now = utcnow()
    today = bogota_midnight(now)
    week_start = today - timedelta(days=6)
    local_now = now.astimezone(BOGOTA)
    month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(today.tzinfo)

    # Tendencia de 7 dias agregada en Python: portable entre SQLite y PostgreSQL
    days = [(week_start + timedelta(days=i)).astimezone(BOGOTA).date() for i in range(7)]
    trend = {day: Decimal(0) for day in days}
    rows = (db.session.query(Order.created_at, Order.total)
            .filter(Order.status.in_(OrderStatus.SALES), Order.created_at >= week_start).all())
    for created_at, total in rows:
        day = bogota_date(as_utc(created_at))
        if day in trend:
            trend[day] += Decimal(total)

    counts = dict(db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all())

    top = (db.session.query(OrderItem.product_name, func.sum(OrderItem.quantity), func.sum(OrderItem.subtotal))
           .join(Order, OrderItem.order_id == Order.id)
           .filter(Order.status.in_(OrderStatus.SALES))
           .group_by(OrderItem.product_name)
           .order_by(func.sum(OrderItem.quantity).desc())
           .limit(5).all())

    low_stock = (Product.query.filter(Product.is_active.is_(True), Product.stock <= Product.min_stock_alert)
                 .order_by(Product.stock.asc(), Product.name.asc()).limit(8).all())

    recent = Order.query.order_by(Order.created_at.desc()).limit(6).all()

    return {
        "sales": {
            "today": money(_sales_since(today)),
            "week": money(_sales_since(week_start)),
            "month": money(_sales_since(month_start)),
        },
        "pending_orders": counts.get(OrderStatus.PENDING, 0),
        "trend": [{"date": d.isoformat(), "label": d.strftime("%d/%m"), "total": money(trend[d])} for d in days],
        "status_counts": [{"status": s, "label": OrderStatus.LABELS[s], "count": counts.get(s, 0)}
                          for s in OrderStatus.ALL],
        "top_products": [{"name": name, "units": int(units or 0), "revenue": money(revenue)}
                         for name, units, revenue in top],
        "low_stock": [{"id": p.id, "name": p.name, "sku": p.sku, "stock": p.stock,
                       "min_stock_alert": p.min_stock_alert} for p in low_stock],
        "recent_orders": [o.summary() for o in recent],
        "totals": {
            "active_products": Product.query.filter_by(is_active=True).count(),
            "orders": sum(counts.values()),
        },
    }
