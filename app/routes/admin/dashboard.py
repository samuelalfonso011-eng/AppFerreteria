from datetime import datetime, timezone, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request
from sqlalchemy import func
from app.decorators import admin_required
from app.extensions import db
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User, Role
from app.models.payment import Payment, PaymentStatus

admin_dashboard_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin')


@admin_dashboard_bp.route('/')
@admin_required
def index():
    """Dashboard administrativo con estadísticas e indicadores reales de PostgreSQL."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

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
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()

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
        recent_orders=recent_orders
    )
