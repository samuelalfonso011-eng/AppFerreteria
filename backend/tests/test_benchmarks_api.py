"""Endpoints /api/admin/benchmarks/*: proteccion, validacion, tope de carga y ultimo resultado."""
import pytest

from app.services import benchmark_service as bench
from tests.conftest import CUSTOMER_PASSWORD
from tests.test_api import checkout_payload


@pytest.fixture(autouse=True)
def isolated_report(tmp_path, monkeypatch):
    """Cada prueba escribe en una carpeta temporal y empieza sin resultado en memoria."""
    monkeypatch.setattr(bench, "REPORT_PATH", str(tmp_path / "benchmark_latest.json"))
    bench._latest.clear()
    yield
    bench._latest.clear()


SMALL = {"sizes": [20, 60], "repetitions": 3, "seed": 42}


def test_benchmarks_require_admin(api):
    assert api.get("/api/admin/benchmarks/latest").status_code == 401
    assert api.post("/api/admin/benchmarks/run", SMALL).status_code == 401
    assert api.login("cliente@ferrepro.test", CUSTOMER_PASSWORD).status_code == 200
    assert api.get("/api/admin/benchmarks/latest").status_code == 403
    assert api.post("/api/admin/benchmarks/run", SMALL).status_code == 403


def test_latest_is_404_before_any_run(admin_api):
    response = admin_api.get("/api/admin/benchmarks/latest")
    assert response.status_code == 404 and response.get_json()["error"] == "no_benchmark"


def test_synthetic_run_returns_full_report_and_latest(admin_api):
    response = admin_api.post("/api/admin/benchmarks/run", SMALL)
    assert response.status_code == 200
    report = response.get_json()
    assert report["meta"]["source"] == "synthetic" and report["meta"]["seed"] == 42
    assert report["meta"]["sizes"] == [20, 60] and report["meta"]["python"]
    assert report["series"]["labels"] == [20, 60]
    assert set(report["series"]["o_n"]) == {"linear_search", "sum_sales", "count_by_customer"}
    assert set(report["series"]["o_n2"]) == {"insertion_sort", "naive_ranking"}
    assert set(report["series"]["o_nlogn"]) == {"merge_sort", "rank_top"}
    assert all(len(v) == 2 for group in ("o_n", "o_n2", "o_nlogn") for v in report["series"][group].values())
    assert len(report["comparison"]) == 4
    row = report["comparison"][0]
    assert {"min_ms", "avg_ms", "median_ms"} <= set(row["before"]) and "speedup" in row
    assert report["equivalence"] == {"sort_by_date": True, "top_products": True, "checked_sizes": [20, 60]}
    assert all(len(m["runs_ms"]) == 3 for m in report["measurements"])
    # Resultados de negocio sobre la base de pruebas (sin pedidos todavia)
    assert report["results"]["orders_count"] == 0 and report["results"]["total_sales"] == "0.00"
    assert report["timing"]["db_fetch_ms"] is not None

    latest = admin_api.get("/api/admin/benchmarks/latest")
    assert latest.status_code == 200 and latest.get_json()["meta"]["run_at"] == report["meta"]["run_at"]


def test_latest_survives_restart_from_report_file(admin_api):
    admin_api.post("/api/admin/benchmarks/run", SMALL)
    bench._latest.clear()  # simula otro worker o un reinicio: lee el archivo
    assert admin_api.get("/api/admin/benchmarks/latest").status_code == 200


def test_real_mode_uses_current_orders_and_business_results(admin_api, api, app):
    from app.models import Product
    with app.app_context():
        pid = Product.query.filter_by(sku="FP-0004").first().id
    for _ in range(3):
        api.post("/api/orders", checkout_payload([{"product_id": pid, "quantity": 2}]))
    report = admin_api.post("/api/admin/benchmarks/run", {"source": "real"}).get_json()
    assert report["series"]["labels"] == [3]
    results = report["results"]
    assert results["orders_count"] == 3 and results["customers_count"] == 1
    assert results["orders_by_customer"] == [{"customer": "laura@example.com", "orders": 3}]
    assert results["search"]["found"] is True and results["search"]["comparisons"] == 3
    # Los pedidos nuevos quedan pendientes: no cuentan como venta confirmada
    assert results["total_sales"] == "0.00" and results["top_products"] == []


def test_run_validates_input_and_safety_cap(admin_api):
    bad = admin_api.post("/api/admin/benchmarks/run", {"sizes": [5, 999999], "repetitions": 9, "source": "x"})
    assert bad.status_code == 400
    assert {"sizes", "repetitions", "source"} <= set(bad.get_json()["fields"])
    too_many = admin_api.post("/api/admin/benchmarks/run", {"sizes": [1, 2, 3, 4, 5, 6, 7]})
    assert too_many.status_code == 400
    over_cap = admin_api.post("/api/admin/benchmarks/run",
                              {"sizes": [5000, 4999, 4998, 4997, 4996, 4995], "repetitions": 5})
    assert over_cap.status_code == 400 and "tope" in over_cap.get_json()["fields"]["sizes"]


def test_concurrent_run_is_rejected(admin_api):
    assert bench._run_lock.acquire(blocking=False)
    try:
        response = admin_api.post("/api/admin/benchmarks/run", SMALL)
        assert response.status_code == 409 and response.get_json()["error"] == "benchmark_running"
    finally:
        bench._run_lock.release()


def test_cli_reproduces_experiment_without_database(tmp_path, capsys):
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "run_benchmarks.py")
    spec = importlib.util.spec_from_file_location("run_benchmarks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "reporte.json"
    report = module.main(["--no-db", "--sizes", "30", "90", "--repetitions", "3", "--output", str(output)])
    printed = capsys.readouterr().out
    assert output.exists() and report["results"] is None
    assert "Equivalencia: orden por fecha OK, ranking OK" in printed
    again = module.main(["--no-db", "--sizes", "30", "90", "--repetitions", "3", "--output", str(output)])
    assert [m["n"] for m in again["measurements"]] == [m["n"] for m in report["measurements"]]
