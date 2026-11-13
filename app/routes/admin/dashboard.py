from datetime import datetime, timezone, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload
from app.decorators import admin_required
from app.extensions import db
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User, Role
from app.models.payment import Payment, PaymentStatus
from app.utils.timezone import now_bogota

admin_dashboard_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin')

def _uploads_size_mb() -> float:
    """Tamaño de la carpeta de imágenes; el recorrido del disco se cachea 10 minutos."""
    from flask import current_app
    from app.utils.cache import cache
    cached = cache.get("maintenance:uploads_mb")
    if cached is not None:
        return cached
    import os
    folder = current_app.config.get('UPLOAD_FOLDER', '')
    size_mb = 0.0
    if folder and os.path.exists(folder):
        total_b = sum(os.path.getsize(os.path.join(r, f)) for r, d, fs in os.walk(folder) for f in fs)
        size_mb = round(total_b / (1024 * 1024), 2)
    cache.set("maintenance:uploads_mb", size_mb, ttl=600)
    return size_mb


@admin_dashboard_bp.route('/')
@admin_required
def index():
    """Dashboard administrativo con estadísticas e indicadores reales de PostgreSQL calculados en hora de Colombia."""
    from app.services.order_service import OrderService
    OrderService.maybe_expire_stale_orders()
    now_col = now_bogota()
    today_start_col = now_col.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = today_start_col.astimezone(timezone.utc)
    week_start = (today_start_col - timedelta(days=now_col.weekday())).astimezone(timezone.utc)
    month_start = today_start_col.replace(day=1).astimezone(timezone.utc)

    # Estados que representan ventas comerciales confirmadas
    confirmed_statuses = [
        OrderStatus.CONFIRMED,
        OrderStatus.PREPARING,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED
    ]

    # 1. Ventas monetarias confirmadas (Excluye cancelados y pagos simulados no aprobados)
    total_sales_query = db.session.query(func.coalesce(func.sum(Order.total), Decimal('0.00')))\
        .filter(Order.status.in_(confirmed_statuses)).scalar() or Decimal('0.00')

    sales_today = db.session.query(func.coalesce(func.sum(Order.total), Decimal('0.00')))\
        .filter(Order.status.in_(confirmed_statuses))\
        .filter(Order.created_at >= today_start).scalar() or Decimal('0.00')

    sales_week = db.session.query(func.coalesce(func.sum(Order.total), Decimal('0.00')))\
        .filter(Order.status.in_(confirmed_statuses))\
        .filter(Order.created_at >= week_start).scalar() or Decimal('0.00')

    sales_month = db.session.query(func.coalesce(func.sum(Order.total), Decimal('0.00')))\
        .filter(Order.status.in_(confirmed_statuses))\
        .filter(Order.created_at >= month_start).scalar() or Decimal('0.00')

    # 2. Conteo de pedidos por estado
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status=OrderStatus.PENDING_CONFIRMATION).count()
    preparing_orders = Order.query.filter_by(status=OrderStatus.PREPARING).count()
    shipped_orders = Order.query.filter_by(status=OrderStatus.SHIPPED).count()
    delivered_orders = Order.query.filter_by(status=OrderStatus.DELIVERED).count()
    cancelled_orders = Order.query.filter_by(status=OrderStatus.CANCELLED).count()

    # 3. Métricas de catálogo e inventario
    total_products = Product.query.count()
    active_products = Product.query.filter_by(is_active=True).count()
    out_of_stock_products = Product.query.filter_by(is_active=True, stock=0).count()
    low_stock_products = Product.query.filter(
        Product.is_active == True,
        Product.stock > 0,
        Product.stock <= Product.min_stock_alert
    ).count()

    # 4. Clientes registrados
    customer_role = Role.query.filter_by(name='customer').first()
    customer_count = User.query.filter_by(role_id=customer_role.id).count() if customer_role else 0

    # 5. Top 5 productos más vendidos en pedidos confirmados
    top_selling = db.session.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label('total_units'),
        func.sum(OrderItem.subtotal).label('total_revenue')
    ).join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.status.in_(confirmed_statuses))\
     .group_by(OrderItem.product_name)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(5).all()

    # 6. Últimos 5 pedidos recibidos
    recent_orders = Order.query.options(joinedload(Order.user)).order_by(Order.created_at.desc()).limit(5).all()

    # 7. Monitoreo de recursos y presupuesto operativo (v1.3.0)
    from app.models.setting import StoreSetting
    from flask import current_app
    import os
    settings = StoreSetting.get_settings()
    monthly_budget = float(settings.monthly_budget_limit or Decimal('5000000.00'))
    usage_pct = round((float(sales_month) / monthly_budget * 100), 1) if monthly_budget > 0 else 0.0

    uploads_mb = _uploads_size_mb()

    resource_stats = {
        "uploads_mb": uploads_mb,
        "monthly_budget": monthly_budget,
        "monthly_sales": float(sales_month),
        "budget_usage_percent": usage_pct,
        "budget_alert": "danger" if usage_pct >= 100 else ("warning" if usage_pct >= 80 else "normal")
    }

    return render_template(
        'admin/dashboard.html',
        total_sales=total_sales_query,
        sales_today=sales_today,
        sales_week=sales_week,
        sales_month=sales_month,
        total_orders=total_orders,
        pending_orders=pending_orders,
        preparing_orders=preparing_orders,
        shipped_orders=shipped_orders,
        delivered_orders=delivered_orders,
        cancelled_orders=cancelled_orders,
        total_products=total_products,
        active_products=active_products,
        out_of_stock_products=out_of_stock_products,
        low_stock_products=low_stock_products,
        customer_count=customer_count,
        top_selling=top_selling,
        recent_orders=recent_orders,
        resource_stats=resource_stats
    )


@admin_dashboard_bp.route('/api/metrics')
@admin_required
def api_metrics():
    """Endpoint REST con métricas agregadas respaldadas por caché para los gráficos interactivos."""
    from app.utils.cache import cache
    cached_metrics = cache.get("admin:dashboard:api:metrics")
    if cached_metrics:
        return cached_metrics

    now_col = now_bogota()
    confirmed_statuses = [
        OrderStatus.CONFIRMED,
        OrderStatus.PREPARING,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED
    ]

    # 1. Ventas por día (últimos 7 días)
    days = [(now_col - timedelta(days=i)).date() for i in range(6, -1, -1)]
    boundaries = [datetime.combine(day, datetime.min.time(), tzinfo=now_col.tzinfo)
                  .astimezone(timezone.utc) for day in days]
    # Siete agregados en una consulta; intervalos semiabiertos en hora de Colombia.
    totals = db.session.query(*[
        func.coalesce(func.sum(case(
            ((Order.created_at >= start) & (Order.created_at < start + timedelta(days=1)), Order.total),
            else_=0)), 0)
        for start in boundaries
    ]).filter(Order.status.in_(confirmed_statuses), Order.created_at >= boundaries[0],
              Order.created_at < boundaries[-1] + timedelta(days=1)).one()
    sales_trend = [
        {"date": day.strftime("%d/%m"), "full_date": str(day), "total": float(total)}
        for day, total in zip(days, totals)
    ]

    # 2. Top 5 productos más vendidos
    top_selling = db.session.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label('total_units'),
        func.sum(OrderItem.subtotal).label('total_revenue')
    ).join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.status.in_(confirmed_statuses))\
     .group_by(OrderItem.product_name)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(5).all()

    top_products = [
        {
            "name": row[0],
            "units": int(row[1] or 0),
            "revenue": float(row[2] or 0.0)
        } for row in top_selling
    ]

    # 3. Distribución de pedidos por estado
    counts = dict(db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all())
    status_counts = {label: counts.get(status, 0) for status, label in OrderStatus.LABELS.items()}

    # 4. Monitoreo de recursos y presupuesto operativo
    from app.models.setting import StoreSetting
    from flask import current_app
    import os
    settings = StoreSetting.get_settings()
    today_start_col = now_col.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start_col.replace(day=1).astimezone(timezone.utc)
    monthly_sales = db.session.query(func.coalesce(func.sum(Order.total), Decimal('0.00')))\
        .filter(Order.status.in_(confirmed_statuses))\
        .filter(Order.created_at >= month_start).scalar() or Decimal('0.00')

    monthly_budget = float(settings.monthly_budget_limit or Decimal('5000000.00'))
    usage_pct = round((float(monthly_sales) / monthly_budget * 100), 1) if monthly_budget > 0 else 0.0

    uploads_mb = _uploads_size_mb()

    data = {
        "sales_trend": sales_trend,
        "top_products": top_products,
        "status_counts": status_counts,
        "orders_by_status": status_counts,
        "resources": {
            "uploads_mb": uploads_mb,
            "total_orders": Order.query.count(),
            "total_products": Product.query.count(),
            "total_users": User.query.count(),
            "monthly_sales": float(monthly_sales),
            "monthly_budget": monthly_budget,
            "budget_usage_percent": usage_pct,
            "budget_alert": "danger" if usage_pct >= 100 else ("warning" if usage_pct >= 80 else "normal")
        },
        "budget_stats": {
            "monthly_sales": float(monthly_sales),
            "monthly_budget": monthly_budget,
            "budget_usage_percent": usage_pct,
            "budget_alert": "danger" if usage_pct >= 100 else ("warning" if usage_pct >= 80 else "normal")
        },
        "storage_stats": {
            "uploads_mb": uploads_mb
        }
    }

    cache.set("admin:dashboard:api:metrics", data, ttl=300)
    return data


@admin_dashboard_bp.route('/buscar')
@admin_required
def search():
    """Buscador global omnicanal del modo admin: busca en pedidos, productos y clientes."""
    from sqlalchemy import or_
    from app.models.category import Category

    q = request.args.get('q', '').strip()
    if not q:
        return render_template(
            'admin/search_results.html',
            q='',
            orders=[],
            products=[],
            customers=[],
            total_results=0,
            order_labels=OrderStatus.LABELS
        )

    # Si es coincidencia exacta de número de pedido (ORD-...)
    exact_order = Order.query.filter(Order.order_number.ilike(q)).first()
    if exact_order:
        return redirect(url_for('admin_orders.detail', order_id=exact_order.id))

    # Si es coincidencia exacta de SKU
    exact_product = Product.query.filter(Product.sku.ilike(q)).first()
    if exact_product:
        return redirect(url_for('admin_products.edit', product_id=exact_product.id))

    # Búsqueda en Pedidos
    orders = Order.query.options(joinedload(Order.user)).join(User).filter(or_(
        Order.order_number.ilike(f"%{q}%"),
        Order.shipping_recipient_name.ilike(f"%{q}%"),
        Order.shipping_phone.ilike(f"%{q}%"),
        Order.shipping_street_address.ilike(f"%{q}%"),
        User.full_name.ilike(f"%{q}%"),
        User.email.ilike(f"%{q}%")
    )).order_by(Order.created_at.desc()).limit(20).all()

    # Búsqueda en Productos
    products = Product.query.options(joinedload(Product.category)).join(Category).filter(or_(
        Product.name.ilike(f"%{q}%"),
        Product.sku.ilike(f"%{q}%"),
        Product.description.ilike(f"%{q}%"),
        Category.name.ilike(f"%{q}%")
    )).order_by(Product.name.asc()).limit(20).all()

    # Búsqueda en Clientes
    customers = User.query.filter(
        User.role.has(name='customer'),
        or_(
            User.full_name.ilike(f"%{q}%"),
            User.email.ilike(f"%{q}%"),
            User.phone.ilike(f"%{q}%")
        )
    ).order_by(User.full_name.asc()).limit(20).all()

    total_results = len(orders) + len(products) + len(customers)

    return render_template(
        'admin/search_results.html',
        q=q,
        orders=orders,
        products=products,
        customers=customers,
        total_results=total_results,
        order_labels=OrderStatus.LABELS
    )

