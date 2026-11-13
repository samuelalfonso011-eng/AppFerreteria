import time
import threading
import logging
from functools import wraps
from sqlalchemy import event
from sqlalchemy.orm import Session
from flask import current_app, has_app_context
from werkzeug.local import LocalProxy

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    Gestor de caché en memoria seguro para hilos con soporte de TTL e invalidación por prefijo.
    Diseñado para almacenar categorías, productos destacados, configuraciones y métricas del dashboard.
    """
    def __init__(self, default_ttl=300):
        self.default_ttl = default_ttl
        self._cache = {}
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                self.misses += 1
                return None
            value, expires_at = entry
            if expires_at is not None and time.time() > expires_at:
                del self._cache[key]
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key: str, value, ttl: int = None):
        with self._lock:
            ttl_seconds = ttl if ttl is not None else self.default_ttl
            expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else None
            self._cache[key] = (value, expires_at)

    def delete(self, key: str):
        with self._lock:
            self._cache.pop(key, None)

    def invalidate_prefix(self, prefix: str):
        """Invalida todas las claves que comiencen con el prefijo especificado."""
        with self._lock:
            keys_to_del = [k for k in self._cache.keys() if k.startswith(prefix)]
            for k in keys_to_del:
                del self._cache[k]
            if keys_to_del:
                logger.debug(f"[CACHE] Invalidadas {len(keys_to_del)} claves con prefijo '{prefix}'")

    def clear(self):
        with self._lock:
            self._cache.clear()
            logger.debug("[CACHE] Limpieza total de caché completada.")

    def get_stats(self) -> dict:
        with self._lock:
            # Purgar expirados antes de reportar
            now = time.time()
            active_keys = [k for k, (_, exp) in self._cache.items() if exp is None or exp > now]
            return {
                "active_entries": len(active_keys),
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio": (self.hits / (self.hits + self.misses)) if (self.hits + self.misses) > 0 else 0.0
            }


def _app_cache():
    if not has_app_context():
        raise RuntimeError("El caché requiere contexto de aplicación")
    return current_app.extensions.setdefault('audit_cache', SimpleCache())


cache = LocalProxy(_app_cache)


def cached(key_prefix: str, ttl: int = 300):
    """
    Decorador para cachear funciones basados en key_prefix y argumentos.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Generar llave basada en argumentos
            arg_str = "_".join(str(a) for a in args)
            kwarg_str = "_".join(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            cache_key = f"{key_prefix}:{arg_str}:{kwarg_str}".strip(":")
            
            cached_val = cache.get(cache_key)
            if cached_val is not None:
                return cached_val

            result = fn(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator


def _collect_invalidations(session, flush_context, instances):
    from app.models import Product, Category, Order, OrderItem, Payment, InventoryMovement, StoreSetting, User
    prefixes = session.info.setdefault('cache_invalidations', set())
    for obj in session.new | session.dirty | session.deleted:
        if isinstance(obj, Product):
            prefixes.update(('products:', 'catalog:', 'admin:dashboard:'))
        elif isinstance(obj, Category):
            prefixes.update(('categories:', 'catalog:', 'products:'))
        elif isinstance(obj, (Order, OrderItem, Payment, InventoryMovement)):
            prefixes.update(('orders:', 'admin:dashboard:', 'products:'))
        elif isinstance(obj, StoreSetting):
            prefixes.update(('store:settings', 'admin:dashboard:'))
        elif isinstance(obj, User):
            prefixes.add('admin:dashboard:')


def _invalidate_after_commit(session):
    for prefix in session.info.pop('cache_invalidations', ()):
        cache.invalidate_prefix(prefix)


def _discard_after_rollback(session):
    session.info.pop('cache_invalidations', None)


def register_cache_invalidation_listeners():
    """Registro idempotente; invalidación después del commit, nunca durante el flush."""
    for name, handler in (
        ('before_flush', _collect_invalidations),
        ('after_commit', _invalidate_after_commit),
        ('after_rollback', _discard_after_rollback),
    ):
        if not event.contains(Session, name, handler):
            event.listen(Session, name, handler)
