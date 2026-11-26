"""Algoritmos explicitos de la Fase 2 (Python puro).

Reglas de esta implementacion:
- No se usa sorted(), list.sort(), heapq ni ORDER BY de SQL: todo ordenamiento esta escrito aqui.
- Las funciones no modifican la lista de entrada; devuelven listas o diccionarios nuevos.
- Los registros son diccionarios simples ("records") para que el costo medido sea solo el
  del algoritmo y no el del ORM.

Clave de orden por fecha: (created_at, id). Desempatar por id hace que el resultado sea
unico aunque dos pedidos compartan fecha, asi Insertion Sort y Merge Sort deben producir
exactamente la misma secuencia de ids.

Complejidades (n = registros, k = productos distintos):
    linear_search_by_id          O(n)        tiempo, O(1) memoria extra
    sum_sales                    O(n)        tiempo, O(1)
    count_orders_by_customer     O(n)        tiempo, O(c) para c clientes
    insertion_sort_by_date       O(n^2)      peor y promedio, O(n) mejor caso (ya ordenado)
    merge_sort / _by_date        O(n log n)  en todos los casos, O(n) memoria extra
    naive_top_products_ranking   O(n*k + k^2) que es O(n^2) cuando k crece con n
    rank_top_selling_items       O(n + k log k)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Hashable, Iterable, Optional

Record = dict[str, Any]
KeyFn = Callable[[Record], Any]


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def date_key(record: Record) -> tuple:
    """Clave de orden por fecha de creacion, con el id como desempate."""
    return (record["created_at"], record["id"])


# ---------------------------------------------------------------------------
# O(n)
# ---------------------------------------------------------------------------

def linear_search_by_id(records: list[Record], target_id: Any) -> tuple[Optional[Record], int]:
    """Busca un registro por id recorriendo la lista de principio a fin.

    Devuelve (registro o None, comparaciones realizadas). Peor caso: el id no existe o es el
    ultimo, n comparaciones. Complejidad O(n).
    """
    comparisons = 0
    for record in records:
        comparisons += 1
        if record["id"] == target_id:
            return record, comparisons
    return None, comparisons


def sum_sales(records: Iterable[Record], field: str = "total",
              statuses: Optional[Iterable[str]] = None) -> Decimal:
    """Suma el importe de las operaciones en una sola pasada. O(n).

    Si se indica statuses, solo suma los registros cuyo "status" este en ese conjunto
    (por ejemplo, solo pedidos confirmados como venta). Usa Decimal para no perder centavos.
    """
    allowed = set(statuses) if statuses is not None else None
    total = Decimal("0")
    for record in records:
        if allowed is not None and record.get("status") not in allowed:
            continue
        total += _as_decimal(record.get(field))
    return total


def count_orders_by_customer(orders: Iterable[Record], key: str = "customer") -> dict[Hashable, int]:
    """Cuenta pedidos por cliente con un diccionario (hash map) en una sola pasada.

    Cada insercion o incremento es O(1) en promedio, asi que el total es O(n).
    """
    counts: dict[Hashable, int] = {}
    for order in orders:
        customer = order.get(key)
        counts[customer] = counts.get(customer, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# O(n^2): linea base ("antes")
# ---------------------------------------------------------------------------

def insertion_sort(items: list[Any], key: Callable[[Any], Any] = lambda x: x, reverse: bool = False) -> list[Any]:
    """Insertion Sort estable. O(n^2) comparaciones y desplazamientos en el peor caso.

    reverse=True ordena de mayor a menor conservando la estabilidad.
    """
    result = list(items)
    for i in range(1, len(result)):
        current = result[i]
        current_key = key(current)
        j = i - 1
        if reverse:
            while j >= 0 and key(result[j]) < current_key:
                result[j + 1] = result[j]
                j -= 1
        else:
            while j >= 0 and key(result[j]) > current_key:
                result[j + 1] = result[j]
                j -= 1
        result[j + 1] = current
    return result


def insertion_sort_by_date(records: list[Record]) -> list[Record]:
    """Ordena por (created_at, id) ascendente con Insertion Sort. O(n^2)."""
    return insertion_sort(records, key=date_key)


def naive_top_products_ranking(order_items: list[Record], limit: Optional[int] = None) -> list[Record]:
    """Ranking ingenuo de productos mas vendidos. O(n*k + k^2), es decir O(n^2).

    1. Para cada item busca linealmente si el producto ya esta en la lista de totales (O(k) por
       item, O(n*k) en total) en lugar de usar un diccionario.
    2. Ordena los k totales con Selection Sort (O(k^2)).
    Sirve como "antes" frente a rank_top_selling_items.
    """
    totals: list[Record] = []
    for item in order_items:
        found = None
        for entry in totals:
            if entry["product_id"] == item["product_id"]:
                found = entry
                break
        if found is None:
            found = {"product_id": item["product_id"], "name": item.get("name", ""), "units": 0,
                     "revenue": Decimal("0")}
            totals.append(found)
        found["units"] += int(item["quantity"])
        found["revenue"] += _as_decimal(item.get("subtotal"))

    # Selection Sort por (-unidades, product_id): mas vendidos primero, desempate estable por id
    ranked = list(totals)
    for i in range(len(ranked)):
        best = i
        for j in range(i + 1, len(ranked)):
            if _ranking_key(ranked[j]) < _ranking_key(ranked[best]):
                best = j
        ranked[i], ranked[best] = ranked[best], ranked[i]
    return ranked[:limit] if limit is not None else ranked


# ---------------------------------------------------------------------------
# O(n log n): optimizado ("despues")
# ---------------------------------------------------------------------------

def merge_sort(items: list[Any], key: Callable[[Any], Any] = lambda x: x, reverse: bool = False) -> list[Any]:
    """Merge Sort estable, de arriba hacia abajo. O(n log n) en todos los casos.

    Divide la lista en mitades hasta tener listas de un elemento y las mezcla en orden.
    La recursion tiene profundidad log2(n), suficiente para millones de elementos.
    reverse=True ordena de mayor a menor y sigue siendo estable.
    """
    n = len(items)
    if n <= 1:
        return list(items)
    middle = n // 2
    left = merge_sort(items[:middle], key, reverse)
    right = merge_sort(items[middle:], key, reverse)
    return _merge(left, right, key, reverse)


def _merge(left: list[Any], right: list[Any], key: Callable[[Any], Any], reverse: bool) -> list[Any]:
    merged: list[Any] = []
    i = j = 0
    while i < len(left) and j < len(right):
        a, b = key(left[i]), key(right[j])
        # Estabilidad: ante empate gana el de la izquierda (llego antes)
        take_left = a >= b if reverse else a <= b
        if take_left:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def merge_sort_by_date(records: list[Record]) -> list[Record]:
    """Ordena por (created_at, id) ascendente con Merge Sort. O(n log n)."""
    return merge_sort(records, key=date_key)


def _ranking_key(entry: Record) -> tuple:
    return (-entry["units"], entry["product_id"])


def rank_top_selling_items(order_items: list[Record], limit: Optional[int] = None) -> list[Record]:
    """Ranking de productos mas vendidos. O(n + k log k).

    1. Acumula unidades e ingresos por producto con un diccionario en una pasada: O(n).
    2. Ordena los k totales con merge_sort por (-unidades, product_id): O(k log k).
    Produce exactamente el mismo resultado que naive_top_products_ranking.
    """
    totals: dict[Hashable, Record] = {}
    for item in order_items:
        entry = totals.get(item["product_id"])
        if entry is None:
            entry = {"product_id": item["product_id"], "name": item.get("name", ""), "units": 0,
                     "revenue": Decimal("0")}
            totals[item["product_id"]] = entry
        entry["units"] += int(item["quantity"])
        entry["revenue"] += _as_decimal(item.get("subtotal"))
    ranked = merge_sort(list(totals.values()), key=_ranking_key)
    return ranked[:limit] if limit is not None else ranked


def top_customers(counts: dict[Hashable, int], limit: int = 10) -> list[Record]:
    """Clientes con mas pedidos a partir del conteo O(n). Ordena con merge_sort: O(c log c)."""
    rows = [{"customer": customer, "orders": total} for customer, total in counts.items()]
    ranked = merge_sort(rows, key=lambda row: (-row["orders"], str(row["customer"])))
    return ranked[:limit]


def median(values: list[float]) -> float:
    """Mediana usando merge_sort (sin sorted()). O(m log m) para m mediciones."""
    if not values:
        return 0.0
    ordered = merge_sort(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
