import time
import threading
import logging
from functools import wraps
from sqlalchemy import event

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


# Instancia singleton de caché
cache = SimpleCache(default_ttl=300)


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


def register_cache_invalidation_listeners():
    """
    Registra listeners automáticos de SQLAlchemy para invalidar el caché
    inmediatamente ante cualquier INSERT, UPDATE o DELETE en la base de datos.
    """
    try:
        from app.models.product import Product
        from app.models.category import Category
        from app.models.order import Order, OrderItem
        from app.models.payment import Payment
        from app.models.inventory import InventoryMovement
        from app.models.setting import StoreSetting

        def on_product_change(mapper, connection, target):
            cache.invalidate_prefix("products:")
            cache.invalidate_prefix("catalog:")
            cache.invalidate_prefix("admin:dashboard:")

        def on_category_change(mapper, connection, target):
            cache.invalidate_prefix("categories:")
            cache.invalidate_prefix("catalog:")
            cache.invalidate_prefix("products:")

        def on_order_change(mapper, connection, target):
            cache.invalidate_prefix("orders:")
            cache.invalidate_prefix("admin:dashboard:")
            cache.invalidate_prefix("products:")

        def on_setting_change(mapper, connection, target):
            cache.invalidate_prefix("store:settings")
            cache.invalidate_prefix("admin:dashboard:")

        # Vincular eventos para Product
        for evt in ('after_insert', 'after_update', 'after_delete'):
            event.listen(Product, evt, on_product_change)
            event.listen(Category, evt, on_category_change)
            event.listen(Order, evt, on_order_change)
            event.listen(OrderItem, evt, on_order_change)
            event.listen(Payment, evt, on_order_change)
            event.listen(InventoryMovement, evt, on_order_change)
            event.listen(StoreSetting, evt, on_setting_change)

        logger.info("[CACHE] Listeners de invalidación automática registrados en modelos SQLAlchemy.")
    except Exception as e:
        logger.warning(f"[CACHE] No se pudieron registrar todos los listeners de caché: {e}")
