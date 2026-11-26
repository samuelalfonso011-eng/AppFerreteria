"""Construcción cronológica de muestras y características compartidas con inferencia."""

import csv
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import func, select

from app.extensions import db
from app.models import Order, OrderStatus, OrderStatusHistory, Product
from app.models.billing import Invoice, InvoiceItem, Payment, PAYMENT_METHODS
from app.models.integrity import LedgerEntry, Verification
from app.models.order import ORDER_CHANNELS
from app.services.errors import BusinessError
from app.utils.timeutils import as_utc, BOGOTA, iso, utcnow


def split_time(times):
    times = sorted(set(times))
    if len(times) < 2:
        raise ValueError("Se requieren dos fechas distintas.")
    return times[min(len(times) - 1, max(1, int(0.8 * len(times))))]


def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("La fecha requiere zona horaria.")
    return as_utc(dt)


def fraud_vector(s):
    angle = timestamp(s["occurred_at"]).astimezone(BOGOTA).hour * math.tau / 24
    return [
        math.log1p(s["amount"]),
        math.log1p(s["prior_frequency"]),
        s["discount_pct"] / 100,
        s["cancellation_rate"],
        int(s["hash_valid"] == 0),
        int(s["hash_valid"] is None),
        math.sin(angle),
        math.cos(angle),
        *(int(s["payment_method"] == m) for m in PAYMENT_METHODS),
        *(int(s["channel"] == c) for c in ORDER_CHANNELS),
    ]


def operation(kind, entity_id):
    model = {"order_id": Order, "invoice_id": Invoice, "payment_id": Payment}[kind]
    obj = db.session.get(model, entity_id)
    if obj is None:
        raise BusinessError("Operación inexistente.", code="not_found", status=404)
    order = obj if kind == "order_id" else db.session.get(Order, obj.order_id)
    payment = obj if kind == "payment_id" else None
    invoice = (
        db.session.get(Invoice, payment.invoice_id) if payment else obj if kind == "invoice_id" else None
    )
    instant = as_utc(obj.created_at)
    employee = invoice.employee_id if invoice else order.employee_id
    identity = Order.customer_id == order.customer_id if order.customer_id else Order.employee_id == employee
    prior = select(Order.id).where(identity, Order.id != order.id, Order.created_at < instant)
    frequency = cancelled = 0
    if order.customer_id or employee:
        frequency = db.session.scalar(select(func.count()).select_from(prior.subquery()))
        cancelled = db.session.scalar(
            select(func.count(func.distinct(OrderStatusHistory.order_id))).where(
                OrderStatusHistory.order_id.in_(prior),
                OrderStatusHistory.new_status == OrderStatus.CANCELLED,
                OrderStatusHistory.created_at < instant,
            )
        )
    # Solo auditorías conocidas al decidir. Una auditoría global comprometida no acusa a otras facturas.
    valid = None
    if invoice:
        link = (
            LedgerEntry.query.filter(
                LedgerEntry.entity_type == "invoice",
                LedgerEntry.entity_id == invoice.id,
                LedgerEntry.created_at <= instant,
            )
            .order_by(LedgerEntry.seq_no.desc())
            .first()
        )
        if link:
            audit = (
                Verification.query.filter(
                    Verification.checked_at >= link.created_at, Verification.checked_at < instant
                )
                .order_by(Verification.id.desc())
                .first()
            )
            if audit and audit.status == "valid" and audit.total_records_checked >= link.seq_no:
                valid = 1
            elif (
                audit
                and audit.first_broken_entity_type == "invoice"
                and audit.first_broken_entity_id == invoice.id
            ):
                valid = 0
    # Recuperar montos originales cuando ya existe la cadena. Cambios posteriores al
    # documento no deben convertirse en variables históricas de entrenamiento.
    discount = invoice.discount_amount if invoice else 0
    subtotal = invoice.subtotal if invoice else 0
    amount = payment.amount if payment else invoice.total_amount if invoice else order.total
    method = payment.payment_method if payment else None
    if invoice:
        issued = (
            LedgerEntry.query.filter_by(entity_type="invoice", entity_id=invoice.id, event_type="issued")
            .order_by(LedgerEntry.seq_no)
            .first()
        )
        if issued and as_utc(issued.created_at) <= instant:
            original = json.loads(issued.canonical_payload)
            discount, subtotal = float(original["discount_amount"]), float(original["subtotal"])
            if not payment:
                amount = original["total_amount"]
    if payment:
        recorded = (
            LedgerEntry.query.filter_by(
                entity_type="payment", entity_id=payment.id, event_type="payment_recorded"
            )
            .order_by(LedgerEntry.seq_no)
            .first()
        )
        if recorded and as_utc(recorded.created_at) <= instant:
            original = json.loads(recorded.canonical_payload)
            amount, method = original["amount"], original["payment_method"]
    return dict(
        order_id=order.id,
        invoice_id=invoice.id if invoice else None,
        payment_id=payment.id if payment else None,
        user_id=order.customer_id,
        employee_id=employee,
        occurred_at=iso(instant),
        amount=float(amount),
        payment_method=method,
        channel=order.channel,
        hash_valid=valid,
        prior_frequency=frequency,
        cancellation_rate=cancelled / frequency if frequency else 0,
        discount_pct=float(100 * discount / subtotal) if subtotal else 0,
    )


def simulated_transactions(seed, cutoff):
    rng = random.Random(seed)
    rows = []
    for i in range(320):
        at = cutoff + timedelta(hours=i - 256)
        suspicious = rng.random() < 0.22
        snapshot = dict(
            occurred_at=iso(at),
            amount=rng.lognormvariate(12 + suspicious, 0.9),
            payment_method=rng.choice(PAYMENT_METHODS),
            channel=rng.choice(ORDER_CHANNELS),
            hash_valid=rng.choice([None, 1, int(not suspicious)]),
            prior_frequency=rng.randrange(80 if suspicious else 25),
            discount_pct=rng.uniform(0, 65 if suspicious else 30),
            cancellation_rate=rng.uniform(0, 0.7 if suspicious else 0.35),
        )
        rows.append((at, fraud_vector(snapshot), int(suspicious), "simulated"))
    return rows


def fraud_dataset(seed):
    dates = [as_utc(d) for d in db.session.scalars(select(Payment.created_at))]
    cutoff = (
        split_time(dates)
        if len(set(dates)) >= 2
        else (dates[0] if dates else datetime(2025, 1, 1, tzinfo=timezone.utc))
    )
    rows, seen = [], set()
    label_file = current_app.config.get("ML_LABEL_FILE")
    late = 0
    if label_file:
        try:
            with open(label_file, encoding="utf-8-sig", newline="") as stream:
                for label in csv.DictReader(stream):
                    pid = int(label["payment_id"])
                    target = {"normal": 0, "fraudulenta": 1}[label["label"]]
                    try:
                        snap = operation("payment_id", pid)
                    except BusinessError as exc:
                        if exc.code != "not_found":
                            raise
                        raise ValueError("Referencia de pago inexistente.") from exc
                    at = timestamp(snap["occurred_at"])
                    decided = timestamp(label["adjudicated_at"])
                    if pid in seen or decided < at or decided > utcnow():
                        raise ValueError("Etiqueta duplicada o fecha de adjudicación inválida.")
                    seen.add(pid)
                    if at < cutoff <= decided:
                        late += 1
                        continue
                    rows.append((at, fraud_vector(snap), target, "real"))
        except (OSError, KeyError, ValueError, csv.Error) as exc:
            raise BusinessError(
                "Revisa las columnas, referencias y fechas del archivo de adjudicaciones.",
                code="invalid_label_file",
                status=422,
            ) from exc
    training_counts = Counter(row[2] for row in rows if row[0] < cutoff)
    simulation = min(training_counts[0], training_counts[1]) < 8
    if simulation:
        rows.extend(simulated_transactions(seed, cutoff))
    rows.sort(key=lambda row: row[0])
    train = [r for r in rows if r[0] < cutoff]
    test = [r for r in rows if r[0] >= cutoff]
    if not test:
        raise BusinessError("Faltan etiquetas posteriores para evaluar.", code="insufficient_test")
    return (
        train,
        test,
        dict(
            cutoff=iso(cutoff),
            real_payments=len(dates),
            adjudicated=len(seen),
            late_labels_excluded=late,
            simulated_labels=simulation,
        ),
    )


def demand_dataset(seed):
    # Unidades brutas facturadas por día de emisión, independientes de anulaciones posteriores.
    counts = defaultdict(Counter)
    today = utcnow().astimezone(BOGOTA).date()
    for pid, at, units in db.session.execute(
        select(InvoiceItem.product_id, Invoice.created_at, InvoiceItem.quantity).join(
            Invoice, Invoice.id == InvoiceItem.invoice_id
        )
    ):
        day = as_utc(at).astimezone(BOGOTA).date()
        if day < today:
            counts[pid][day] += units
    days = sorted({d for counter in counts.values() for d in counter})
    real_days = len(days)
    simulation = not days or (days[-1] - days[0]).days < 13
    if simulation:
        rng = random.Random(seed)
        counts.clear()
        start = date(2025, 1, 1)
        for pid in (-1, -2):
            for i in range(90):
                counts[pid][start + timedelta(days=i)] = max(
                    0, round(10 - pid * 2 + i * 0.12 + 3 * math.sin(i * math.tau / 7) + rng.gauss(0, 1.2))
                )
    end = max(max(c) for c in counts.values())
    start = min(min(c) for c in counts.values())
    calendar = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    cutoff = split_time(calendar)
    series = {}
    names = dict(db.session.execute(select(Product.id, Product.name)).all()) if not simulation else {}
    for pid, counter in sorted(counts.items()):
        dates = [d for d in calendar if d >= min(counter)]
        if sum(d < cutoff for d in dates) < 3:
            continue
        series[str(pid)] = dict(
            name=names.get(pid, f"Producto simulado {abs(pid)}"),
            start=dates[0].isoformat(),
            values=[counter[d] for d in dates],
        )
    if not series:
        raise BusinessError("Historial de demanda insuficiente.", code="insufficient_history")
    return (
        series,
        cutoff,
        dict(
            source="simulated" if simulation else "real",
            real_sale_days=real_days,
            excluded_products=len(counts) - len(series),
            cutoff=cutoff.isoformat(),
        ),
    )


def demand_vector(day, history, lead=1, known=None):
    angle = day.weekday() * math.tau / 7
    known = len(history) if known is None else known
    recent = history[max(0, known - 7) : known]
    return [
        recent[-1],
        sum(recent) / len(recent),
        known + lead - 1,
        math.sin(angle),
        math.cos(angle),
        math.log1p(lead),
    ]
