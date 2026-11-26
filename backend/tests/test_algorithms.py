"""Correctitud de los algoritmos de la Fase 2 (sin base de datos)."""
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services import algorithms_service as alg
from app.services.benchmark_service import synthetic_dataset

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def rec(id_, minutes, total="10.00", customer="a@x.com", status="CONFIRMED"):
    return {"id": id_, "created_at": BASE + timedelta(minutes=minutes), "total": Decimal(total),
            "customer": customer, "status": status, "order_number": f"FP-{id_}"}


def item(product_id, quantity, subtotal="0", name=None):
    return {"product_id": product_id, "quantity": quantity, "subtotal": Decimal(subtotal), "name": name or f"P{product_id}"}


def reference_order(records):
    # Referencia independiente para comparar (en las pruebas si se permite sorted)
    return [r["id"] for r in sorted(records, key=lambda r: (r["created_at"], r["id"]))]


# ---------------------------------------------------------------- O(n)

def test_linear_search_finds_and_counts_comparisons():
    records = [rec(5, 1), rec(9, 2), rec(2, 3)]
    found, comparisons = alg.linear_search_by_id(records, 9)
    assert found["id"] == 9 and comparisons == 2
    missing, comparisons = alg.linear_search_by_id(records, 99)
    assert missing is None and comparisons == 3
    assert alg.linear_search_by_id([], 1) == (None, 0)


def test_sum_sales_uses_decimal_and_filters_statuses():
    records = [rec(1, 0, "0.10"), rec(2, 0, "0.20"), rec(3, 0, "5.00", status="CANCELLED")]
    assert alg.sum_sales(records) == Decimal("5.30")
    assert alg.sum_sales(records, statuses=["CONFIRMED"]) == Decimal("0.30")  # sin error de punto flotante
    assert alg.sum_sales([]) == Decimal("0")


def test_count_orders_by_customer_single_pass():
    orders = [rec(1, 0, customer="a"), rec(2, 0, customer="b"), rec(3, 0, customer="a")]
    assert alg.count_orders_by_customer(orders) == {"a": 2, "b": 1}
    assert alg.count_orders_by_customer([]) == {}


# ---------------------------------------------------------------- ordenamiento

@pytest.mark.parametrize("sorter", [alg.insertion_sort_by_date, alg.merge_sort_by_date])
def test_sorts_handle_empty_single_and_ties(sorter):
    assert sorter([]) == []
    one = [rec(1, 0)]
    assert sorter(one) == one and sorter(one) is not one
    tied = [rec(3, 5), rec(1, 5), rec(2, 1)]  # misma fecha: desempata por id
    assert [r["id"] for r in sorter(tied)] == [2, 1, 3]


@pytest.mark.parametrize("sorter", [alg.insertion_sort_by_date, alg.merge_sort_by_date])
def test_sorts_do_not_mutate_input(sorter):
    data = [rec(1, 9), rec(2, 1), rec(3, 5)]
    before = [r["id"] for r in data]
    sorter(data)
    assert [r["id"] for r in data] == before


def test_insertion_and_merge_sort_are_equivalent_on_random_inputs():
    rng = random.Random(7)
    for size in (0, 1, 2, 3, 10, 57, 300):
        data = [rec(i, rng.randrange(0, 50)) for i in rng.sample(range(1, 10_000), size)]
        insertion = [r["id"] for r in alg.insertion_sort_by_date(data)]
        merge = [r["id"] for r in alg.merge_sort_by_date(data)]
        assert insertion == merge == reference_order(data)


def test_generic_sorts_support_reverse_and_are_stable():
    pairs = [(2, "a"), (1, "b"), (2, "c"), (1, "d")]
    for sorter in (alg.insertion_sort, alg.merge_sort):
        assert sorter(pairs, key=lambda p: p[0]) == [(1, "b"), (1, "d"), (2, "a"), (2, "c")]
        assert sorter(pairs, key=lambda p: p[0], reverse=True) == [(2, "a"), (2, "c"), (1, "b"), (1, "d")]


def test_synthetic_dataset_is_deterministic_and_equivalent():
    a, b = synthetic_dataset(500, 42), synthetic_dataset(500, 42)
    assert [r["id"] for r in a.orders] == [r["id"] for r in b.orders]
    assert [r["created_at"] for r in a.orders] == [r["created_at"] for r in b.orders]
    assert synthetic_dataset(500, 43).orders[0]["created_at"] != a.orders[0]["created_at"]
    assert [r["id"] for r in alg.insertion_sort_by_date(a.orders)] == [r["id"] for r in alg.merge_sort_by_date(a.orders)]


# ---------------------------------------------------------------- ranking

def reference_ranking(items):
    units, revenue = Counter(), {}
    for it in items:
        units[it["product_id"]] += it["quantity"]
        revenue[it["product_id"]] = revenue.get(it["product_id"], Decimal("0")) + it["subtotal"]
    return [(pid, units[pid], revenue[pid]) for pid in sorted(units, key=lambda p: (-units[p], p))]


def signature(ranking):
    return [(r["product_id"], r["units"], r["revenue"]) for r in ranking]


def test_rankings_match_reference_and_each_other():
    items = [item(3, 2, "20"), item(1, 5, "50"), item(2, 5, "40"), item(3, 4, "40"), item(4, 1, "9")]
    expected = reference_ranking(items)
    assert signature(alg.rank_top_selling_items(items)) == expected
    assert signature(alg.naive_top_products_ranking(items)) == expected
    # Empate en 5 unidades entre 1 y 2: gana el id menor; el 3 suma 6 y va primero
    assert [r["product_id"] for r in alg.rank_top_selling_items(items)] == [3, 1, 2, 4]


def test_rankings_on_random_synthetic_items_and_limits():
    data = synthetic_dataset(2500, 42)
    expected = reference_ranking(data.items)
    assert signature(alg.rank_top_selling_items(data.items)) == expected
    assert signature(alg.naive_top_products_ranking(data.items)) == expected
    assert len(alg.rank_top_selling_items(data.items, limit=5)) == 5
    assert alg.rank_top_selling_items([]) == alg.naive_top_products_ranking([]) == []


def test_top_customers_and_median():
    counts = {"b": 2, "a": 2, "c": 5}
    assert alg.top_customers(counts, limit=2) == [{"customer": "c", "orders": 5}, {"customer": "a", "orders": 2}]
    assert alg.median([3.0, 1.0, 2.0]) == 2.0
    assert alg.median([4.0, 1.0, 3.0, 2.0]) == 2.5
    assert alg.median([]) == 0.0


def test_evaluated_modules_do_not_use_builtin_sorting():
    """Revisa el arbol de sintaxis (no el texto): comentarios y docstrings no cuentan."""
    import ast
    import inspect
    from app.services import benchmark_service

    for module in (alg, benchmark_service):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                assert not (isinstance(func, ast.Name) and func.id == "sorted"), f"sorted() en {module.__name__}"
                assert not (isinstance(func, ast.Attribute) and func.attr in ("sort", "order_by")), \
                    f".{getattr(func, 'attr', '')}() en {module.__name__}"
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
                assert "heapq" not in names, f"heapq en {module.__name__}"
