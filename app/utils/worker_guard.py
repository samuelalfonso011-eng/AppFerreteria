import functools
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from app.extensions import db

logger = logging.getLogger(__name__)

# Timeout máximo obligatorio para workers y tareas secundarias
MAX_TASK_TIMEOUT = 15  # segundos


class WorkerTimeoutError(Exception):
    """Excepción lanzada cuando una tarea o worker supera el tiempo máximo permitido."""
    pass


def run_guarded_task(task_func, *args, timeout_seconds=MAX_TASK_TIMEOUT, **kwargs):
    """
    Ejecuta una tarea con timeout forzado, manejo de recursos y liberación obligatoria de db.session.
    Previene procesos zombies y bloqueos indefinidos en la base de datos o en workers.
    """
    timeout = min(timeout_seconds, MAX_TASK_TIMEOUT)

    def _wrapper():
        try:
            return task_func(*args, **kwargs)
        finally:
            # Liberación estricta de conexiones y descriptores
            try:
                db.session.remove()
            except Exception as e:
                logger.warning(f"Error al limpiar db.session en guarded task: {e}")

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_wrapper)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            logger.error(f"Worker timeout: Tarea '{task_func.__name__}' excedió el límite de {timeout}s.")
            raise WorkerTimeoutError(f"La tarea '{task_func.__name__}' excedió el tiempo máximo de ejecución ({timeout}s).")
        except Exception as e:
            logger.error(f"Error en worker task '{task_func.__name__}': {e}")
            raise e


def guarded_worker(timeout_seconds=MAX_TASK_TIMEOUT):
    """
    Decorador para workers, tareas cron o funciones en segundo plano.
    Garantiza que la función nunca se ejecute por más de `timeout_seconds`
    y siempre libere las conexiones a PostgreSQL.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def decorated(*args, **kwargs):
            return run_guarded_task(fn, *args, timeout_seconds=timeout_seconds, **kwargs)
        return decorated
    return decorator
