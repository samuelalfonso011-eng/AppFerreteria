"""Motor de benchmarks reproducible de la Fase 2.

Que mide y como:
- db_fetch_ms: tiempo de leer pedidos e items desde la base (Supabase/PostgreSQL), una vez.
- compute_ms: tiempo puro de cada algoritmo con time.perf_counter(), sobre datos ya en memoria.
  Cada algoritmo se ejecuta `repetitions` veces por tamano y se reportan min, promedio y mediana.
- Datos "synthetic": lotes deterministas generados con random.Random(f"{seed}:{n}"); la misma
  semilla produce exactamente los mismos registros en cualquier maquina.
- Datos "real": los pedidos actuales de la base, en un solo punto N = cantidad de pedidos.
- Equivalencia obligatoria: Insertion Sort y Merge Sort deben devolver los mismos ids en el mismo
  orden, y el ranking ingenuo debe coincidir con el optimizado. Si no, se lanza AssertionError
  (con una comprobacion explicita que no desaparece con python -O).

El speedup se calcula con medianas: speedup = mediana O(n^2) / mediana O(n log n).
"""
from __future__ import annotations

import json
import os
import platform
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from app.services import algorithms_service as alg

DEFAULT_SIZES = (100, 500, 1000, 2500, 5000)
DEFAULT_SEED = 42
DEFAULT_REPETITIONS = 3
MIN_SIZE, MAX_SIZE, MAX_SIZES = 10, 5000, 6
MIN_REPETITIONS, MAX_REPETITIONS = 3, 5
SALES_STATUSES = ("CONFIRMED", "PREPARING", "SHIPPED", "DELIVERED")
REPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "reports", "benchmark_latest.json")

_run_lock = threading.Lock()
_latest: dict[str, Any] = {}


class BenchmarkBusy(RuntimeError):
    """Ya hay un benchmark en curso en este proceso."""


@dataclass
class Dataset:
    orders: list[dict]
    items: list[dict]
    db_fetch_ms: Optional[float] = None
    source: str = "synthetic"
    notes: list[str] = field(default_factory=list)


def _require(condition: bool, message: str) -> None:
    # Equivale a assert, pero sigue activo aunque Python corra con -O
    if not condition:
        raise AssertionError(message)


def _round(value: float, digits: int = 4) -> float:
    return round(value, digits)


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------

def synthetic_dataset(n: int, seed: int = DEFAULT_SEED) -> Dataset:
    """Lote determinista de n pedidos y n items.

    Clientes: n/5 (cada cliente repite pedidos). Productos: entre 5 y 200 (k crece con n,
    lo que hace visible el costo O(n*k) del ranking ingenuo). Las fechas cubren dos anos y
    algunas se repiten a proposito para ejercitar el desempate por id.
    """
    rng = random.Random(f"{seed}:{n}")
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    customers = max(1, n // 5)
    products = max(5, min(200, n // 10))
    statuses = ("CONFIRMED", "DELIVERED", "SHIPPED", "PREPARING", "PENDING_CONFIRMATION", "CANCELLED")
    weights = (30, 30, 10, 10, 15, 5)
    orders: list[dict] = []
    for i in range(1, n + 1):
        seconds = rng.randrange(0, 2 * 365 * 24 * 3600)
        if i > 1 and rng.random() < 0.02:
            seconds = int((orders[-1]["created_at"] - start).total_seconds())  # fecha repetida
        orders.append({
            "id": i,
            "order_number": f"SIM-{i:06d}",
            "created_at": start + timedelta(seconds=seconds),
            "total": Decimal(rng.randrange(1_000_000, 200_000_000)) / 100,
            "status": rng.choices(statuses, weights)[0],
            "customer": f"cliente{rng.randrange(customers):05d}@example.com",
        })
    items: list[dict] = []
    for i in range(n):
        product_id = rng.randrange(1, products + 1)
        quantity = rng.randrange(1, 6)
        price = Decimal(rng.randrange(500_000, 50_000_000)) / 100
        items.append({"product_id": product_id, "name": f"Producto {product_id}", "quantity": quantity,
                      "subtotal": price * quantity, "status": "CONFIRMED"})
    return Dataset(orders, items, None, "synthetic")


def load_real_data() -> Dataset:
    """Lee pedidos e items de la base (requiere contexto de aplicacion). Sin ORDER BY."""
    from app.extensions import db
    from app.models import Order, OrderItem
    from app.utils.timeutils import as_utc

    started = time.perf_counter()
    order_rows = db.session.query(Order.id, Order.order_number, Order.created_at, Order.total,
                                  Order.status, Order.customer_email).all()
    item_rows = (db.session.query(OrderItem.product_id, OrderItem.product_name, OrderItem.quantity,
                                  OrderItem.subtotal, Order.status)
                 .join(Order, OrderItem.order_id == Order.id).all())
    from app.models import Product
    # Nombre actual del catálogo para el ranking; el de la línea solo si el producto ya no existe
    current = dict(db.session.query(Product.id, Product.name).all())
    db_fetch_ms = (time.perf_counter() - started) * 1000

    orders = [{"id": r.id, "order_number": r.order_number, "created_at": as_utc(r.created_at),
               "total": r.total, "status": r.status, "customer": (r.customer_email or "").strip().lower()}
              for r in order_rows]
    items = [{"product_id": r.product_id, "name": current.get(r.product_id, r.product_name), "quantity": r.quantity,
              "subtotal": r.subtotal, "status": r.status} for r in item_rows]
    return Dataset(orders, items, _round(db_fetch_ms), "real")


# ---------------------------------------------------------------------------
# Medicion
# ---------------------------------------------------------------------------

def _measure(fn: Callable[[], Any], repetitions: int) -> tuple[Any, dict]:
    runs: list[float] = []
    result = None
    for _ in range(repetitions):
        started = time.perf_counter()
        result = fn()
        runs.append((time.perf_counter() - started) * 1000)
    return result, {
        "min_ms": _round(min(runs)),
        "avg_ms": _round(sum(runs) / len(runs)),
        "median_ms": _round(alg.median(runs)),
        "runs_ms": [_round(run) for run in runs],
    }


ALGORITHMS = (
    # clave, nombre visible, complejidad, grupo de la serie
    ("linear_search", "Búsqueda lineal por ID", "O(n)", "o_n"),
    ("sum_sales", "Suma de ventas", "O(n)", "o_n"),
    ("count_by_customer", "Pedidos por cliente (hash map)", "O(n)", "o_n"),
    ("insertion_sort", "Insertion Sort por fecha", "O(n^2)", "o_n2"),
    ("naive_ranking", "Ranking ingenuo de productos", "O(n^2)", "o_n2"),
    ("merge_sort", "Merge Sort por fecha", "O(n log n)", "o_nlogn"),
    ("rank_top", "Ranking con hash map + Merge Sort", "O(n log n)", "o_nlogn"),
)
PAIRS = (
    ("Ordenar pedidos por fecha", "insertion_sort", "merge_sort"),
    ("Ranking de productos más vendidos", "naive_ranking", "rank_top"),
)


def _ranking_signature(ranking: list[dict]) -> list[tuple]:
    return [(row["product_id"], row["units"], row["revenue"]) for row in ranking]


def _bench_size(data: Dataset, repetitions: int) -> tuple[dict, dict]:
    orders, items = data.orders, data.items
    target = orders[-1]["id"] if orders else None  # peor caso de la busqueda lineal: el ultimo
    calls = {
        "linear_search": lambda: alg.linear_search_by_id(orders, target),
        "sum_sales": lambda: alg.sum_sales(orders, statuses=SALES_STATUSES),
        "count_by_customer": lambda: alg.count_orders_by_customer(orders),
        "insertion_sort": lambda: alg.insertion_sort_by_date(orders),
        "naive_ranking": lambda: alg.naive_top_products_ranking(items),
        "merge_sort": lambda: alg.merge_sort_by_date(orders),
        "rank_top": lambda: alg.rank_top_selling_items(items),
    }
    results, stats = {}, {}
    for key, *_ in ALGORITHMS:
        results[key], stats[key] = _measure(calls[key], repetitions)

    _require([r["id"] for r in results["insertion_sort"]] == [r["id"] for r in results["merge_sort"]],
             "Insertion Sort y Merge Sort no produjeron el mismo orden de ids")
    _require(_ranking_signature(results["naive_ranking"]) == _ranking_signature(results["rank_top"]),
             "El ranking ingenuo y el optimizado no coinciden")
    return stats, results


def _speedup(before: float, after: float) -> Optional[float]:
    return _round(before / after, 2) if after > 0 else None


def run_benchmark(source: str = "synthetic", sizes=DEFAULT_SIZES, repetitions: int = DEFAULT_REPETITIONS,
                  seed: int = DEFAULT_SEED, real: Optional[Dataset] = None,
                  search_id: Optional[int] = None, report_path: Optional[str] = None) -> dict:
    """Ejecuta el experimento completo y devuelve el reporte (ver PHASE2_API.md).

    real: datos reales ya cargados; si se omite, los resultados de negocio quedan en null.
    """
    if not _run_lock.acquire(blocking=False):
        raise BenchmarkBusy("Ya hay un benchmark en ejecución.")
    try:
        started = time.perf_counter()
        if source == "real":
            datasets = [(len(real.orders), real)] if real is not None else []
        else:
            datasets = [(n, synthetic_dataset(n, seed)) for n in sizes]

        measurements, comparison = [], []
        series: dict[str, dict[str, list]] = {"o_n": {}, "o_n2": {}, "o_nlogn": {}}
        for key, _, _, group in ALGORITHMS:
            series[group][key] = []
        labels = []
        for n, data in datasets:
            stats, _ = _bench_size(data, repetitions)
            labels.append(n)
            for key, label, complexity, group in ALGORITHMS:
                series[group][key].append(stats[key]["median_ms"])
                measurements.append({"n": n, "algorithm": key, "label": label, "complexity": complexity, **stats[key]})
            for operation, before, after in PAIRS:
                b, a = stats[before]["median_ms"], stats[after]["median_ms"]
                speedup = _speedup(b, a)
                comparison.append({
                    "n": n, "operation": operation,
                    "before": {"algorithm": before, "complexity": "O(n^2)", **{k: stats[before][k] for k in ("min_ms", "avg_ms", "median_ms")}},
                    "after": {"algorithm": after, "complexity": "O(n log n)", **{k: stats[after][k] for k in ("min_ms", "avg_ms", "median_ms")}},
                    "speedup": speedup,
                    "improvement_pct": _round((1 - a / b) * 100, 1) if b > 0 else None,
                })

        report = {
            "meta": environment(source, list(labels), repetitions, seed),
            "timing": {
                "db_fetch_ms": real.db_fetch_ms if real is not None else None,
                "compute_ms": _round((time.perf_counter() - started) * 1000, 1),
            },
            "series": {"labels": labels, **series},
            "comparison": comparison,
            "measurements": measurements,
            "equivalence": {"sort_by_date": True, "top_products": True, "checked_sizes": labels},
            "results": business_results(real, search_id) if real is not None else None,
        }
        target = report_path or REPORT_PATH
        report["meta"]["report_file"] = "backend/reports/benchmark_latest.json" if target == REPORT_PATH else os.path.basename(target)
        if save_latest(report, target) is None:
            report["meta"]["report_file"] = None  # solo quedo en memoria
        return report
    finally:
        _run_lock.release()


def business_results(data: Dataset, search_id: Optional[int] = None) -> dict:
    """Resultados de negocio sobre los datos reales, usando los algoritmos de este modulo."""
    sales_items = [item for item in data.items if item["status"] in SALES_STATUSES]
    counts = alg.count_orders_by_customer(data.orders)
    target = search_id if search_id is not None else (data.orders[-1]["id"] if data.orders else None)
    found, comparisons = alg.linear_search_by_id(data.orders, target)
    ordered = alg.merge_sort_by_date(data.orders)
    _require([r["id"] for r in alg.insertion_sort_by_date(data.orders)] == [r["id"] for r in ordered],
             "Insertion Sort y Merge Sort no coinciden sobre los datos reales")
    _require(_ranking_signature(alg.naive_top_products_ranking(sales_items)) ==
             _ranking_signature(alg.rank_top_selling_items(sales_items)),
             "Los rankings no coinciden sobre los datos reales")
    return {
        "orders_count": len(data.orders),
        "items_count": len(data.items),
        "total_sales": str(alg.sum_sales(data.orders, statuses=SALES_STATUSES).quantize(Decimal("0.01"))),
        "sales_statuses": list(SALES_STATUSES),
        "top_products": [{"product_id": r["product_id"], "name": r["name"], "units": r["units"],
                          "revenue": str(r["revenue"].quantize(Decimal("0.01")))}
                         for r in alg.rank_top_selling_items(sales_items, limit=5)],
        "customers_count": len(counts),
        "orders_by_customer": alg.top_customers(counts, limit=10),
        "search": {
            "target_id": target, "found": found is not None, "comparisons": comparisons,
            "order_number": found["order_number"] if found else None,
            "total": str(found["total"]) if found else None,
        },
        "first_order_at": ordered[0]["created_at"].isoformat().replace("+00:00", "Z") if ordered else None,
        "last_order_at": ordered[-1]["created_at"].isoformat().replace("+00:00", "Z") if ordered else None,
    }


def environment(source: str, sizes: list, repetitions: int, seed: int) -> dict:
    clock = time.get_clock_info("perf_counter")
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": source,
        "seed": seed,
        "sizes": sizes,
        "repetitions": repetitions,
        "timer": {"name": "time.perf_counter", "resolution_s": clock.resolution},
        "argv": " ".join(sys.argv[1:]) or None,
    }


# ---------------------------------------------------------------------------
# Ultimo resultado: memoria del proceso y archivo (sobrevive reinicios y varios workers)
# ---------------------------------------------------------------------------

def save_latest(report: dict, path: Optional[str] = None) -> Optional[str]:
    path = path or REPORT_PATH  # se lee al llamar: las pruebas lo redirigen a una carpeta temporal
    _latest.clear()
    _latest.update(report)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
        return path
    except OSError:
        return None  # sistema de archivos de solo lectura (por ejemplo, el contenedor): queda en memoria


def load_latest(path: Optional[str] = None) -> Optional[dict]:
    path = path or REPORT_PATH
    if _latest:
        return dict(_latest)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None
