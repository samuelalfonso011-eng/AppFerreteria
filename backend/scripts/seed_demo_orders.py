"""Crea pedidos de demostración identificables para analítica y entrenamiento.

Uso (desde backend/):
    venv\\Scripts\\python scripts\\seed_demo_orders.py --count 200 --days 60
    venv\\Scripts\\python scripts\\seed_demo_orders.py --dry-run      (simula y revierte)

Qué crea:
- Cuentas demo inactivas (no pueden iniciar sesión): clientes y empleados con correo @ejemplo.test.
- Pedidos repartidos en los últimos `--days` días (sin el día actual, que la demanda omite), con
  estados variados, la nota "Datos de demostración" y su historial de estados fechado.
- Facturas y pagos para los pedidos vendidos. Las fechas se fijan ANTES de sellar cada documento en
  integrity_ledger, así la cadena sigue siendo válida. Facturas y pagos quedan permanentes en la cadena.
- Una reposición de stock registrada en el kárdex cuando hace falta.

Las etiquetas de fraude no se inventan: sin adjudicaciones reales el clasificador sigue usando el
corpus simulado documentado en PHASE5_API.md.
"""
from __future__ import annotations

import argparse
import math
import random
import secrets
import sys
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Order, OrderItem, OrderStatus, Product, StoreSetting, User  # noqa: E402
from app.models.billing import Invoice, InvoiceItem, Payment  # noqa: E402
from app.models.consent import POLICY_VERSION  # noqa: E402
from app.models.inventory import MovementType  # noqa: E402
from app.models.order import OrderStatusHistory  # noqa: E402
from app.services import integrity_service, inventory_service  # noqa: E402
from app.utils.timeutils import BOGOTA  # noqa: E402

DEMO_NOTE = "Datos de demostración"
DEMO_DOMAIN = "@ejemplo.test"
CUSTOMERS = ["Laura Gómez", "Andrés Ruiz", "Camila Torres", "Mateo Rojas", "Valentina Díaz", "Santiago López",
             "Isabella Castro", "Julián Moreno", "Mariana Vargas", "Sebastián Pardo", "Daniela Ríos", "Tomás Herrera"]
EMPLOYEES = ["Caja Centro (demo)", "Caja Norte (demo)"]
CITIES = [("Antioquia", "Medellín", "Laureles"), ("Cundinamarca", "Bogotá", "Chapinero"),
          ("Valle del Cauca", "Cali", "Granada"), ("Atlántico", "Barranquilla", "El Prado")]
# Estados finales: vendidos, en curso, cancelados y unos pocos pendientes recientes
STATUS_WEIGHTS = [(OrderStatus.DELIVERED, 34), (OrderStatus.SHIPPED, 14), (OrderStatus.PREPARING, 10),
                  (OrderStatus.CONFIRMED, 14), (OrderStatus.CANCELLED, 13)]
CHANNEL_WEIGHTS = [("web", 45), ("presencial", 25), ("app", 15), ("domicilio", 15)]
PATH = {  # recorrido de estados hasta el final
    OrderStatus.CONFIRMED: [OrderStatus.CONFIRMED],
    OrderStatus.PREPARING: [OrderStatus.CONFIRMED, OrderStatus.PREPARING],
    OrderStatus.SHIPPED: [OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.SHIPPED],
    OrderStatus.DELIVERED: [OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.SHIPPED, OrderStatus.DELIVERED],
}
CENT = Decimal("0.01")


def pick(rng, weighted):
    total = sum(w for _, w in weighted)
    roll = rng.uniform(0, total)
    for value, weight in weighted:
        roll -= weight
        if roll <= 0:
            return value
    return weighted[-1][0]


def demo_account(email, name, role):
    user = User.query.filter_by(email=email).one_or_none()
    if user is None:
        user = User(email=email, full_name=name, role=role, is_active=False)
        user.set_password(secrets.token_urlsafe(32))  # contraseña aleatoria descartada: nadie puede entrar
        db.session.add(user)
        db.session.flush()
    return user


def plan_days(rng, count, days, today):
    """Pedidos por día con tendencia leve, más ventas el fin de semana y ruido: una serie con forma."""
    weights = []
    for offset in range(days, 0, -1):
        day = today - timedelta(days=offset)
        trend = 1 + 0.6 * (days - offset) / days
        weekend = 1.35 if day.weekday() >= 5 else 1.0
        weights.append((day, trend * weekend * rng.uniform(0.7, 1.3)))
    total = sum(w for _, w in weights)
    plan = [(day, math.floor(count * w / total)) for day, w in weights]
    missing = count - sum(n for _, n in plan)
    for i in range(missing):
        day, n = plan[-1 - (i % len(plan))]
        plan[-1 - (i % len(plan))] = (day, n + 1)
    return plan


def at(day, rng, start_hour=8, end_hour=19):
    local = datetime.combine(day, time(rng.randint(start_hour, end_hour), rng.randint(0, 59), rng.randint(0, 59)),
                             tzinfo=BOGOTA)
    return local.astimezone(timezone.utc)


def seed(count, days, seed_value, admin_id):
    rng = random.Random(seed_value)
    now = datetime.now(timezone.utc)
    today = now.astimezone(BOGOTA).date()
    products = Product.query.filter_by(is_active=True).order_by(Product.id).all()
    if not products:
        raise SystemExit("No hay productos activos.")
    customers = [demo_account(f"cliente.demo{i + 1}{DEMO_DOMAIN}", name, User.ROLE_CUSTOMER)
                 for i, name in enumerate(CUSTOMERS)]
    employees = [demo_account(f"empleado.demo{i + 1}{DEMO_DOMAIN}", name, User.ROLE_EMPLOYEE)
                 for i, name in enumerate(EMPLOYEES)]
    settings = StoreSetting.get()

    pending_count = max(4, count // 20)  # pendientes recientes: el panel los vence a las 48 h
    plan = plan_days(rng, count - pending_count, days, today)
    jobs = [(day, None) for day, n in plan for _ in range(n)]
    jobs += [(today - timedelta(days=1 if i % 2 else 0), OrderStatus.PENDING) for i in range(pending_count)]

    # Reposición previa: unidades suficientes para todo el lote, registradas en el kárdex
    lines_per_order = [[(rng.choice(products), rng.choices([1, 1, 1, 2, 2, 3])[0])
                        for _ in range(rng.choices([1, 1, 2, 2, 3])[0])] for _ in jobs]
    need = {}
    for lines in lines_per_order:
        for product, qty in lines:
            need[product.id] = need.get(product.id, 0) + qty
    for product in products:
        missing = need.get(product.id, 0) + 5 - product.stock
        if missing > 0:
            inventory_service.increase(product, missing, MovementType.ADJUSTMENT_IN,
                                       "Reposición para datos de demostración", user_id=admin_id, reference="DEMO")
    db.session.commit()

    summary = {"orders": 0, "invoices": 0, "payments": 0, "voided": 0}
    for (day, forced), lines in zip(jobs, lines_per_order):
        status = forced or pick(rng, STATUS_WEIGHTS)
        channel = pick(rng, CHANNEL_WEIGHTS)
        staff = channel in ("presencial", "domicilio")
        employee = rng.choice(employees) if staff else None
        customer = rng.choice(customers) if rng.random() < 0.75 else None
        name = customer.full_name if customer else rng.choice(CUSTOMERS)
        email = customer.email if customer else f"invitado.demo{rng.randint(1, 999)}{DEMO_DOMAIN}"
        department, city, neighborhood = rng.choice(CITIES)
        created = at(day, rng) if forced is None else now - timedelta(hours=rng.randint(1, 20))
        merged = {}
        for product, qty in lines:
            merged[product.id] = (product, merged.get(product.id, (product, 0))[1] + qty)
        subtotal = sum((Decimal(p.price) * q for p, q in merged.values()), Decimal("0"))
        shipping = Decimal("0.00") if channel == "presencial" else settings.calculate_shipping(subtotal)
        number = "FP-" + created.astimezone(BOGOTA).strftime("%y%m%d") + "-" + secrets.token_hex(3).upper()
        order = Order(order_number=number, status=OrderStatus.PENDING, subtotal=subtotal, shipping_cost=shipping,
                      total=subtotal + shipping, channel=channel, customer_id=customer.id if customer else None,
                      employee_id=employee.id if employee else None, customer_name=name, customer_email=email,
                      customer_phone=f"300{rng.randint(1000000, 9999999)}", doc_type="CC",
                      doc_number=str(rng.randint(10000000, 1099999999)), department=department, city=city,
                      neighborhood=neighborhood, street_address=f"Calle {rng.randint(1, 120)} # {rng.randint(1, 90)}-{rng.randint(1, 99)}",
                      notes=DEMO_NOTE, policy_version=POLICY_VERSION, terms_accepted_at=created,
                      privacy_accepted_at=created, created_at=created, updated_at=created)
        db.session.add(order)
        db.session.flush()
        for product, qty in merged.values():
            inventory_service.decrease(product, qty, MovementType.SALE_EXIT, f"Venta del pedido {number} (demo)",
                                       user_id=employee.id if employee else None, reference=number)
            order.items.append(OrderItem(product_id=product.id, product_name=product.name, product_sku=product.sku,
                                         unit_price=product.price, quantity=qty, subtotal=Decimal(product.price) * qty))
        actor = employee.id if employee else admin_id
        clock = created
        db.session.add(OrderStatusHistory(order_id=order.id, previous_status=None, new_status=OrderStatus.PENDING,
                                          changed_by_user_id=employee.id if employee else None,
                                          comment=f"Pedido registrado por canal {channel}. {DEMO_NOTE}.", created_at=clock))
        summary["orders"] += 1

        voided = status == OrderStatus.CANCELLED and rng.random() < 0.35  # algunos se facturan y luego se anulan
        if status in PATH or voided:
            clock += timedelta(minutes=rng.randint(10, 120))
            discount = Decimal("0.00")
            if rng.random() < 0.25:
                rate = Decimal(rng.choice([5, 10, 15]))
                if employee is employees[-1] and rng.random() < 0.5:
                    rate = Decimal(rng.choice([25, 35]))  # un operador con descuentos altos para la analítica
                discount = (subtotal * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
            invoice = Invoice(order_id=order.id, employee_id=actor, subtotal=subtotal, shipping_cost=shipping,
                              tax_amount=Decimal("0.00"), discount_amount=discount,
                              total_amount=subtotal - discount + shipping, created_at=clock,
                              items=[InvoiceItem(product_id=i.product_id, name=i.product_name, sku=i.product_sku,
                                                 quantity=i.quantity, unit_price=i.unit_price, subtotal=i.subtotal)
                                     for i in order.items])
            db.session.add(invoice)
            integrity_service.append_event("invoice", invoice, "issued")
            summary["invoices"] += 1
            previous = OrderStatus.PENDING
            for step in (PATH.get(status) or [OrderStatus.CONFIRMED]):
                clock += timedelta(hours=rng.randint(2, 30)) if step != OrderStatus.CONFIRMED else timedelta(0)
                db.session.add(OrderStatusHistory(order_id=order.id, previous_status=previous, new_status=step,
                                                  changed_by_user_id=actor, comment=DEMO_NOTE, created_at=clock))
                previous = step
            order.status = previous
            if voided:
                clock += timedelta(hours=rng.randint(1, 12))
                invoice.status = "anulada"
                integrity_service.append_event("invoice", invoice, "voided")
                summary["voided"] += 1
            elif status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED) or rng.random() < 0.5:
                # Vendidos: pagados (a veces en dos partes). Pedidos en curso: a veces con una transferencia pendiente.
                total = invoice.total_amount
                parts = [total] if rng.random() < 0.8 or total < 2 else [
                    (total / 2).quantize(CENT), total - (total / 2).quantize(CENT)]
                settled = status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED)
                for amount in parts:
                    method = rng.choice(["efectivo", "tarjeta"] if staff else ["tarjeta", "transferencia", "pse", "nequi"])
                    clock += timedelta(minutes=rng.randint(5, 240))
                    instant = method in ("efectivo", "tarjeta")
                    payment = Payment(invoice_id=invoice.id, order_id=order.id, amount=amount, payment_method=method,
                                      status="aprobado" if instant else "pendiente",
                                      paid_at=clock if instant else None, created_at=clock)
                    db.session.add(payment)
                    integrity_service.append_event("payment", payment, "payment_recorded")
                    if not instant and settled:  # confirmación posterior del dinero recibido
                        payment.status = "aprobado"
                        payment.paid_at = clock + timedelta(hours=rng.randint(1, 20))
                        integrity_service.append_event("payment", payment, "adjustment")
                    summary["payments"] += 1
        if status == OrderStatus.CANCELLED:
            clock += timedelta(hours=rng.randint(1, 24))
            db.session.add(OrderStatusHistory(order_id=order.id, previous_status=order.status,
                                              new_status=OrderStatus.CANCELLED, changed_by_user_id=actor,
                                              comment=f"Cancelado. {DEMO_NOTE}.", created_at=clock))
            order.status = OrderStatus.CANCELLED
            inventory_service.restore_for_order(order, actor, f"Cancelación del pedido {number} (demo)")
        order.updated_at = clock
        db.session.commit()
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--dry-run", action="store_true", help="Simula y revierte (no guarda nada).")
    args = parser.parse_args(argv)
    if not 20 <= args.count <= 2000 or not 14 <= args.days <= 365:
        parser.error("Usa entre 20 y 2000 pedidos y entre 14 y 365 días.")
    app = create_app()
    with app.app_context():
        admin = User.query.filter_by(role=User.ROLE_ADMIN, is_active=True).order_by(User.id).first()
        if admin is None:
            raise SystemExit("Se necesita una cuenta de administrador activa.")
        if args.dry_run:
            # Todo en una transacción que se revierte: commits intermedios desactivados
            db.session.commit = db.session.flush  # type: ignore[method-assign]
            try:
                print(seed(args.count, args.days, args.seed, admin.id))
            finally:
                db.session.rollback()
            print("Simulación revertida: no se guardó nada.")
            return
        print(seed(args.count, args.days, args.seed, admin.id))


if __name__ == "__main__":
    main()
