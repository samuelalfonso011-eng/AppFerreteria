"""Estadística descriptiva con interpolación lineal y regresión por mínimos cuadrados."""
from collections import Counter, defaultdict
from datetime import timedelta
from math import ceil, floor, sqrt

from sqlalchemy import select, text

from app.extensions import db
from app.models import Order, OrderItem, OrderStatus, Product, User
from app.models.analytics import AnomalyAlert
from app.models.billing import Invoice
from app.utils.timeutils import as_utc, BOGOTA


def boxplot(values):
    ordered = sorted(values)
    if not ordered:
        return None

    def quantile(p):
        h = (len(ordered) - 1) * p
        return ordered[floor(h)] + (ordered[ceil(h)] - ordered[floor(h)]) * (h - floor(h))

    q1, median, q3 = (quantile(p) for p in (0.25, 0.5, 0.75))
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = [v for v in ordered if lower <= v <= upper]
    return dict(n=len(ordered), q1=q1, median=median, q3=q3, iqr=iqr, lower=lower, upper=upper,
                whisker_min=inside[0], whisker_max=inside[-1], outliers=[v for v in ordered if v < lower or v > upper])


def local_day(timestamp):
    return as_utc(timestamp).astimezone(BOGOTA).date()


MIN_HISTORY = 4  # observaciones previas mínimas antes de juzgar una operación


def user_analytics(persist=False):
    """Perfiles, boxplots y alertas. GET calcula sin escribir; persist=True (POST) sincroniza anomaly_alerts."""
    if persist and db.session.get_bind().dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(617203582)"))
    users = db.session.execute(select(User.id, User.role, User.full_name).where(
        User.role.in_(("customer", "employee"))).order_by(User.id)).all()
    orders = db.session.execute(select(Order.id, Order.customer_id, Order.channel, Order.total,
                                       Order.status, Order.created_at).where(Order.customer_id.is_not(None))
                                .order_by(Order.created_at, Order.id)).all()
    invoices = db.session.execute(select(Invoice.id, Invoice.employee_id, Invoice.subtotal, Invoice.total_amount,
                                         Invoice.discount_amount, Invoice.status, Invoice.created_at)
                                  .order_by(Invoice.created_at, Invoice.id)).all()
    customer_orders, employee_invoices = defaultdict(list), defaultdict(list)
    for order in orders:
        customer_orders[order.customer_id].append(order)
    for invoice in invoices:
        employee_invoices[invoice.employee_id].append(invoice)
    days = [local_day(row.created_at) for row in orders]
    window = (max(days) - min(days)).days + 1 if days else 0
    invoice_days = [local_day(row.created_at) for row in invoices]
    invoice_window = (max(invoice_days) - min(invoice_days)).days + 1 if invoice_days else 0
    profiles, findings = [], {}
    totals = defaultdict(list)

    def flag(profile, kind, distribution, samples, explanation):
        if not distribution or distribution["n"] < 4:
            return
        high = distribution["upper"]
        triggers = [(value, ids) for value, ids in samples if value > high and ids]
        if not triggers:
            return
        excess = max(v for v, _ in triggers) - high
        scale = distribution["iqr"] or max(abs(high), 1)
        score = round(100 * excess / (excess + scale), 2)
        key = (profile["user_id"], profile["user_role"], kind)
        if key in findings and score <= findings[key]["anomaly_score"]:
            return
        record_ids = sorted({i for _, ids in triggers for i in ids})
        source = "order_ids" if profile["user_role"] == "customer" else "invoice_ids"
        findings[key] = dict(anomaly_score=score, threshold_info=distribution,
                             explanation=f"{explanation}. Valor máximo {high + excess:.2f}, límite {high:.2f}.",
                             source_record_ids={source: record_ids})

    def flag_history(profile, kind, samples, explanation):
        """Cada operación se compara solo con las anteriores de la misma cuenta (orden cronológico).

        Una cerca calculada con todo el historial usaría compras posteriores para juzgar una anterior.
        Se necesitan MIN_HISTORY observaciones previas; la alerta conserva la cerca vigente en el caso
        de mayor puntaje y lista todas las operaciones que superaron su propia cerca.
        """
        best, record_ids = None, []
        for i in range(MIN_HISTORY, len(samples)):
            value, record_id = samples[i]
            distribution = boxplot([v for v, _ in samples[:i]])
            high = distribution["upper"]
            if value <= high:
                continue
            excess = value - high
            scale = distribution["iqr"] or max(abs(high), 1)
            score = round(100 * excess / (excess + scale), 2)
            record_ids.append(record_id)
            if best is None or score > best[0]:
                best = (score, distribution, value)
        if best is None:
            return
        score, distribution, value = best
        key = (profile["user_id"], profile["user_role"], kind)
        if key in findings and score <= findings[key]["anomaly_score"]:
            return
        source = "order_ids" if profile["user_role"] == "customer" else "invoice_ids"
        findings[key] = dict(anomaly_score=score, threshold_info=distribution,
                             explanation=f"{explanation}. Valor {value:.2f}, límite {distribution['upper']:.2f} "
                                         f"según las {distribution['n']} operaciones anteriores.",
                             source_record_ids={source: sorted(set(record_ids))})

    for user in users:
        role = user.role
        rows = customer_orders[user.id] if role == "customer" else employee_invoices[user.id]
        count = len(rows)
        profile = dict(user_id=user.id, user_role=role, name=user.full_name, operations_count=count)
        operations = []
        for row in rows:
            amount = float(row.total if role == "customer" else row.total_amount)
            operations.append(dict(id=row.id, amount=amount, status=row.status))
        amounts = [op["amount"] for op in operations]
        totals[role].extend(amounts)
        profile.update(operations=operations, amount_boxplot=boxplot(amounts))
        cancelled = [row.id for row in rows if row.status in (OrderStatus.CANCELLED, "anulada")]
        profile["cancellation_rate"] = len(cancelled)/count if count else None
        if role == "customer":
            channels = Counter(row.channel for row in rows)
            profile.update(orders_per_day=count/window if window else None,
                           predominant_channel=min(channels, key=lambda ch: (-channels[ch], ch)) if channels else None)
        else:
            discounts = [dict(invoice_id=row.id, amount=float(row.discount_amount),
                              percent=float(100*row.discount_amount/row.subtotal) if row.subtotal else None)
                         for row in rows]
            profile.update(invoices_issued=count, discounts=discounts,
                           invoices_per_day=count / invoice_window if invoice_window else None)
            flag_history(profile, "abusive_discounts",
                         [(d["percent"], d["invoice_id"]) for d in discounts if d["percent"] is not None],
                         "Descuento superior al historial previo del empleado (%)")
        flag_history(profile, "high_amount_outlier", [(op["amount"], op["id"]) for op in operations],
                     "Monto superior al historial previo de la cuenta (COP)")
        profiles.append(profile)

    for role in ("customer", "employee"):
        active = [p for p in profiles if p["user_role"] == role and p["operations_count"]]
        # Frecuencia como tasa diaria sobre la misma ventana: el total de operaciones favorecería
        # a las cuentas más antiguas.
        frequency = "orders_per_day" if role == "customer" else "invoices_per_day"
        for field, kind, label in (
            (frequency, "unusual_frequency", "Frecuencia diaria superior a otras cuentas activas del rol"),
            ("cancellation_rate", "excessive_cancellations", "Proporción de anulaciones superior al grupo"),
        ):
            distribution = boxplot([p[field] for p in active])
            for profile in active:
                ids = [op["id"] for op in profile["operations"] if kind != "excessive_cancellations"
                       or op["status"] in (OrderStatus.CANCELLED, "anulada")]
                flag(profile, kind, distribution, [(profile[field], ids)], label)

    # Un empleado que aplica descuentos altos de forma uniforme puede no ser atípico
    # respecto de sí mismo. Contrastar también el promedio con el de sus pares.
    discount_peers = []
    for profile in profiles:
        if profile["user_role"] == "employee":
            records = [d for d in profile["discounts"] if d["percent"] is not None]
            if records:
                average = sum(d["percent"] for d in records) / len(records)
                discount_peers.append((profile, average, records))
    distribution = boxplot([average for _, average, _ in discount_peers])
    for profile, average, records in discount_peers:
        ids = [d["invoice_id"] for d in records if d["percent"] > 0]
        flag(profile, "abusive_discounts", distribution, [(average, ids)],
             "Porcentaje medio de descuento superior al de otros empleados")

    current = {(a.user_id, a.user_role, a.alert_type): a for a in AnomalyAlert.query.all()}
    if persist:
        alerts = []
        for key, attrs in findings.items():
            alert = current.pop(key, None)
            if alert is None:
                alert = AnomalyAlert(user_id=key[0], user_role=key[1], alert_type=key[2])
                db.session.add(alert)
            for field, value in attrs.items():
                setattr(alert, field, value)
            alerts.append(alert)
        for stale in current.values():
            db.session.delete(stale)
        db.session.commit()
        reports = [a.report() for a in alerts]
    else:
        # Lectura pura: mismas alertas calculadas, con el ID y la fecha de la fila guardada si ya existe.
        reports = []
        for key, attrs in findings.items():
            saved = current.get(key)
            reports.append(dict(id=saved.id if saved else None, user_id=key[0], user_role=key[1], alert_type=key[2],
                                threshold_info=attrs["threshold_info"], explanation=attrs["explanation"],
                                source_record_ids=attrs["source_record_ids"],
                                anomaly_score=float(attrs["anomaly_score"]),
                                created_at=saved.report()["created_at"] if saved else None))
    return dict(profiles=profiles, global_boxplots={role: boxplot(totals[role]) for role in ("customer","employee")},
                customer_window_days=window, alerts=reports)


def fit(values):
    """OLS para x = 0, 1, ..., n-1."""
    x_mean = (len(values)-1)/2
    y_mean = sum(values)/len(values)
    slope = sum((i-x_mean)*(v-y_mean) for i,v in enumerate(values))/sum((i-x_mean)**2 for i in range(len(values)))
    return slope, y_mean - slope*x_mean


def regression(values, horizon):
    n = len(values)
    training = max(2, int(n*0.8)) if n >= 3 else n
    result = dict(short_series=n < 5, train_periods=training, test_periods=n-training,
                  model=None, forecast_model=None, estimates=[None]*n, forecast=[],
                  metrics={"mae": None, "rmse": None, "r2": None})
    if n < 2:
        return result
    slope, intercept = fit(values[:training])
    result["model"] = dict(slope=slope, intercept=intercept)
    estimates = [intercept + slope*i for i in range(n)]
    result["estimates"] = estimates
    test = values[training:]
    if test:
        errors = [val-pred for val,pred in zip(test, estimates[training:])]
        squared = sum(e*e for e in errors)
        mean = sum(test)/len(test)
        variance = sum((v-mean)**2 for v in test)
        result["metrics"] = dict(mae=sum(abs(e) for e in errors)/len(test), rmse=sqrt(squared/len(test)),
                                 r2=1-squared/variance if variance else None)
    slope, intercept = fit(values)
    result["forecast_model"] = dict(slope=slope, intercept=intercept)
    result["forecast"] = [max(0, intercept + slope*i) for i in range(n, n+horizon)]
    return result


def demand(period, horizon, product_id=None):
    step = timedelta(days=7 if period == "weekly" else 1)
    query = (select(Order.created_at, OrderItem.product_id, OrderItem.quantity)
             .join(OrderItem, OrderItem.order_id == Order.id).where(
                 Order.status.in_(OrderStatus.SALES),
                 ~select(Invoice.id).where(Invoice.order_id == Order.id, Invoice.status == "anulada").exists()))
    quantities = defaultdict(Counter)
    overall = Counter()
    for timestamp, pid, units in db.session.execute(query):
        day = local_day(timestamp)
        if period == "weekly":
            day -= timedelta(days=day.weekday())
        quantities[pid][day] += units
        overall[day] += units

    def series(counts):
        dates = []
        if counts:
            day, last = min(counts), max(overall)
            while day <= last:
                dates.append(day)
                day += step
        values = [counts[day] for day in dates]
        result = regression(values, horizon)
        estimates = result.pop("estimates")
        result["history"] = [dict(period=day.isoformat(), observed=values[i], estimated=estimates[i],
                                  split="train" if i < result["train_periods"] else "test")
                             for i,day in enumerate(dates)]
        result["forecast"] = [dict(period=(dates[-1]+step*i).isoformat(), predicted=value)
                              for i,value in enumerate(result["forecast"],1)]
        return result

    products = select(Product.id, Product.name).order_by(Product.id)
    if product_id is not None:
        products = products.where(Product.id == product_id)
    return {"period": period, "horizon": horizon, "global": series(overall),
            "products": [dict(product_id=pid, name=name, **series(quantities[pid]))
                         for pid,name in db.session.execute(products)]}
