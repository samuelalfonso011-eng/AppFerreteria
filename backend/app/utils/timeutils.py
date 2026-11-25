"""Fechas siempre en UTC en la base de datos; los cortes de dia se calculan en hora de Colombia."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Colombia no usa horario de verano: UTC-5 fijo, sin depender de tzdata en Windows.
BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso(value):
    value = as_utc(value)
    return value.isoformat().replace("+00:00", "Z") if value else None


def bogota_midnight(now=None):
    """Inicio del dia actual en Colombia, expresado en UTC."""
    local = (now or utcnow()).astimezone(BOGOTA)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def bogota_date(value):
    return as_utc(value).astimezone(BOGOTA).date()


def money(value):
    """Pesos colombianos: entero si no hay centavos, para que el JSON sea limpio."""
    amount = Decimal(value or 0)
    return int(amount) if amount == amount.to_integral_value() else float(amount)
