"""Cache de lectura con invalidacion automatica.

Tres capas, replicadas y mejoradas del proyecto anterior:
1. SimpleCache: memoria por proceso, segura entre hilos, con TTL e invalidacion por prefijo.
2. CacheVersion: un token por ambito (catalog, store) guardado en la base de datos. Las claves
   llevan el token; cualquier escritura de producto, categoria, inventario o pedido lo cambia
   dentro de la misma transaccion. Asi la invalidacion es correcta aunque haya varios workers.
3. HTTP: ETag fuerte + Cache-Control: no-cache. El navegador revalida en cada visita y recibe
   un 304 sin cuerpo cuando nada cambio; en cuanto cambia el token, el ETag cambia.
"""
import hashlib
import json
import logging
import threading
import time
import uuid

from flask import current_app, has_app_context, request
from sqlalchemy import event
from sqlalchemy.orm import Session
from werkzeug.local import LocalProxy

from app.extensions import db

logger = logging.getLogger(__name__)

SCOPE_CATALOG = "catalog"
SCOPE_STORE = "store"


class SimpleCache:
    def __init__(self, default_ttl=300, max_entries=2000):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._data = {}
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self.misses += 1
                return None
            value, expires_at = entry
            if expires_at is not None and time.monotonic() > expires_at:
                del self._data[key]
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key, value, ttl=None):
        ttl = self.default_ttl if ttl is None else ttl
        with self._lock:
            if len(self._data) >= self.max_entries:
                self._purge_expired()
                if len(self._data) >= self.max_entries:
                    self._data.pop(next(iter(self._data)))
            self._data[key] = (value, time.monotonic() + ttl if ttl > 0 else None)

    def invalidate_prefix(self, prefix):
        with self._lock:
            keys = [k for k in self._data if k.startswith(prefix)]
            for key in keys:
                del self._data[key]
        if keys:
            logger.debug("[CACHE] %s claves invalidadas con prefijo %s", len(keys), prefix)

    def clear(self):
        with self._lock:
            self._data.clear()

    def stats(self):
        with self._lock:
            total = self.hits + self.misses
            return {"entries": len(self._data), "hits": self.hits, "misses": self.misses,
                    "hit_ratio": round(self.hits / total, 3) if total else 0.0}

    def _purge_expired(self):
        now = time.monotonic()
        for key in [k for k, (_, exp) in self._data.items() if exp is not None and exp < now]:
            del self._data[key]


def _store():
    if not has_app_context():
        raise RuntimeError("La cache requiere contexto de aplicacion")
    return current_app.extensions.setdefault(
        "ferrepro_cache", SimpleCache(current_app.config.get("CACHE_TTL", 300)))


cache = LocalProxy(_store)


def current_token(scope):
    from app.models import CacheVersion
    row = db.session.get(CacheVersion, scope)
    return row.token if row else "0"


def memo(scope, key, builder, ttl=None):
    """Devuelve (payload, body, etag, hit). La clave se versiona con el token del ambito."""
    scopes = scope if isinstance(scope, (tuple, list)) else (scope,)
    token = ".".join(current_token(s) for s in scopes)
    full_key = f"{key}@{token}"
    entry = cache.get(full_key)
    hit = entry is not None
    if not hit:
        payload = builder()
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        etag = hashlib.sha256(body.encode("utf-8")).hexdigest()[:40]
        entry = (payload, body, etag)
        cache.set(full_key, entry, ttl)
    payload, body, etag = entry
    return payload, body, etag, hit


def cached_json_response(scope, key, builder, ttl=None):
    """Respuesta JSON cacheada con ETag y respuesta 304 condicional."""
    _, body, etag, hit = memo(scope, key, builder, ttl)
    response = current_app.response_class(body, mimetype="application/json")
    response.set_etag(etag)
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return response.make_conditional(request)


# ---------------------------------------------------------------------------
# Invalidacion automatica ligada a la transaccion
# ---------------------------------------------------------------------------

def _scopes_for(obj):
    from app.models import (Category, InventoryMovement, Order, OrderItem, OrderStatusHistory, Product,
                            StoreSetting)
    # El historial se incluye porque un cambio de estado se aplica con UPDATE condicional
    # (sin marcar el Order como modificado) y siempre agrega una fila de historial.
    if isinstance(obj, (Product, Category, InventoryMovement, Order, OrderItem, OrderStatusHistory)):
        return (SCOPE_CATALOG,)
    if isinstance(obj, StoreSetting):
        return (SCOPE_STORE,)
    return ()


def _bump_tokens(session, flush_context, instances):
    from app.models import CacheVersion
    scopes = set()
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        scopes.update(_scopes_for(obj))
    if not scopes:
        return
    pending = session.info.setdefault("cache_scopes", set())
    with session.no_autoflush:
        for scope in scopes:
            row = session.get(CacheVersion, scope)
            if row is None:
                row = CacheVersion(scope=scope, token="")
                session.add(row)
            row.token = uuid.uuid4().hex
            pending.add(scope)


def _after_commit(session):
    scopes = session.info.pop("cache_scopes", ())
    if scopes and has_app_context():
        for scope in scopes:
            cache.invalidate_prefix(scope + ":")


def _after_rollback(session):
    session.info.pop("cache_scopes", None)


def register_cache_listeners():
    """Registro idempotente. El token cambia en el flush; la memoria local se limpia tras el commit."""
    for name, handler in (("before_flush", _bump_tokens),
                          ("after_commit", _after_commit),
                          ("after_rollback", _after_rollback)):
        if not event.contains(Session, name, handler):
            event.listen(Session, name, handler)


def ensure_cache_rows():
    from app.models import CacheVersion
    for scope in (SCOPE_CATALOG, SCOPE_STORE):
        if db.session.get(CacheVersion, scope) is None:
            db.session.add(CacheVersion(scope=scope, token=uuid.uuid4().hex))
