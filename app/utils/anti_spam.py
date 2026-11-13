import time
import re
import threading
import logging
from collections import defaultdict
from flask import request, current_app, abort, render_template
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

logger = logging.getLogger(__name__)

# Almacén en memoria seguro para Rate Limiting por IP: { "ip:action": [timestamp, ...] }
_rate_limits = defaultdict(list)


def get_serializer():
    secret = current_app.config['SECRET_KEY']
    return URLSafeTimedSerializer(secret, salt='ferreteria-anti-spam')


def generate_form_token() -> str:
    """Genera un token firmado con la hora actual para validar tiempo de llenado."""
    serializer = get_serializer()
    return serializer.dumps(time.time())


def is_honeypot_triggered(form_data: dict, field_name: str = "website_url") -> bool:
    """
    Verifica si el campo trampa (honeypot) fue completado por un bot automatizado.
    Retorna True si fue completado (es spam), False si está vacío.
    """
    val = form_data.get(field_name, '')
    if val and str(val).strip():
        logger.warning("[ANTI-SPAM] Honeypot activado")
        return True
    return False


def is_submitted_too_fast(token: str, min_seconds: float = 2.0) -> bool:
    """
    Verifica si el formulario se envió en menos de `min_seconds` desde su renderizado.
    Retorna True si fue demasiado rápido (comportamiento de bot), False si es humano.
    """
    # En entorno de pruebas automatizadas omitimos la restricción temporal si no hay token
    if current_app.config.get('TESTING'):
        if not token:
            return False

    if not token:
        return True

    serializer = get_serializer()
    try:
        created_at = serializer.loads(token, max_age=3600)  # Válido máximo 1 hora
        elapsed = time.time() - created_at
        if elapsed < min_seconds:
            logger.warning(f"[ANTI-SPAM] Envío ultrarrápido detectado: {elapsed:.2f}s (< {min_seconds}s)")
            return True
        return False
    except (BadSignature, SignatureExpired) as e:
        logger.warning(f"[ANTI-SPAM] Firma de token inválida o expirada: {e}")
        return True


_rate_lock = threading.Lock()
_last_purge = 0.0


def _rate_enforced() -> bool:
    """En pruebas automatizadas el límite solo se aplica si ENFORCE_RATE_LIMIT está activo."""
    return not (current_app.config.get('TESTING') and not current_app.config.get('ENFORCE_RATE_LIMIT'))


def _client_ip() -> str:
    # remote_addr ya refleja X-Forwarded-For SOLO a través de ProxyFix (proxy de confianza).
    # Leer la cabecera directamente permitiría a cualquier cliente falsificar su IP y evadir el límite.
    return request.remote_addr or '127.0.0.1'


def _rate_key(action: str, identity: str = None) -> str:
    # Con identidad (p. ej. correo) el contador es global para esa identidad, no por IP,
    # para frenar también ataques distribuidos contra una misma cuenta.
    return f"id:{identity}:{action}" if identity else f"{_client_ip()}:{action}"


def _purge_stale(now: float, max_window: int = 3600):
    """Elimina claves inactivas para que el almacén en memoria no crezca sin límite."""
    global _last_purge
    if now - _last_purge < 60:
        return
    _last_purge = now
    for k in [k for k, v in _rate_limits.items() if not v or now - v[-1] > max_window]:
        del _rate_limits[k]


def check_rate_limit(action: str, limit: int = 5, window_seconds: int = 60, identity: str = None) -> bool:
    """
    Consume un intento de `action` para la IP actual (o `identity`).
    Retorna True si está permitido, False si superó la tasa máxima (HTTP 429).
    Nota: el almacén es en memoria por proceso; con varios workers el límite efectivo es por worker.
    """
    if not _rate_enforced():
        return True

    key = _rate_key(action, identity)
    now = time.time()
    with _rate_lock:
        _purge_stale(now)
        _rate_limits[key] = [ts for ts in _rate_limits[key] if now - ts < window_seconds]
        if len(_rate_limits[key]) >= limit:
            logger.warning(f"[ANTI-SPAM] Rate limit excedido en acción '{action}' ({len(_rate_limits[key])}/{limit})")
            return False
        _rate_limits[key].append(now)
        return True


def is_rate_limited(action: str, limit: int, window_seconds: int, identity: str = None) -> bool:
    """Consulta sin consumir: True si ya se alcanzó el límite de intentos registrados."""
    if not _rate_enforced():
        return False
    key = _rate_key(action, identity)
    now = time.time()
    with _rate_lock:
        return len([ts for ts in _rate_limits.get(key, []) if now - ts < window_seconds]) >= limit


def register_hit(action: str, identity: str = None):
    """Registra un evento (p. ej. un login fallido) sin comprobar el límite."""
    if not _rate_enforced():
        return
    with _rate_lock:
        _rate_limits[_rate_key(action, identity)].append(time.time())


def clear_hits(action: str, identity: str = None):
    """Borra los eventos registrados (p. ej. tras un login exitoso)."""
    with _rate_lock:
        _rate_limits.pop(_rate_key(action, identity), None)


def reset_rate_limits():
    """Vacía todos los contadores (útil en pruebas)."""
    with _rate_lock:
        _rate_limits.clear()

def contains_excessive_links(text: str, max_links: int = 2) -> bool:
    """
    Detecta inyecciones de spam masivo o múltiples URLs en mensajes.
    Retorna True si contiene más hipervínculos que max_links.
    """
    if not text:
        return False
    pattern = r'(https?://|www\.|\b[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}/|\[url\])'
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    return len(matches) > max_links


def render_rate_limit_error(message: str = "Has alcanzado el límite de intentos permitidos. Por favor espera unos minutos."):
    """Retorna una respuesta HTTP 429 amigable."""
    return render_template('errors/429.html', message=message), 429
