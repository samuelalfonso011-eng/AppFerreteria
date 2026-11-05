"""
Módulo de manejo y conversión de zona horaria oficial para Colombia (America/Bogota, UTC-5).
Garantiza que todas las fechas y horas mostradas en la interfaz reflejen la hora local real.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BOGOTA_TZ = ZoneInfo("America/Bogota")


def now_bogota() -> datetime:
    """Devuelve la fecha y hora actual en la zona horaria de Bogotá (UTC-5)."""
    return datetime.now(BOGOTA_TZ)


def to_bogota(dt: datetime | None) -> datetime | None:
    """Convierte un objeto datetime (naive UTC o aware) a America/Bogota."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BOGOTA_TZ)


def format_bogota(dt: datetime | None, fmt: str = "%d/%m/%Y %I:%M %p") -> str:
    """Formatea un datetime en hora de Bogotá, Colombia con sufijos en español."""
    local_dt = to_bogota(dt)
    if local_dt is None:
        return ""
    formatted = local_dt.strftime(fmt)
    return formatted.replace("AM", "a. m.").replace("PM", "p. m.")
