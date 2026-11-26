"""Reproduce el experimento de la Fase 2 desde la terminal.

Uso (desde backend/):
    venv\\Scripts\\python scripts\\run_benchmarks.py
    venv\\Scripts\\python scripts\\run_benchmarks.py --repetitions 5 --sizes 100 500 1000 2500 5000
    venv\\Scripts\\python scripts\\run_benchmarks.py --source real
    venv\\Scripts\\python scripts\\run_benchmarks.py --no-db          (solo datos sinteticos, sin base)

Imprime la tabla Antes vs Despues y guarda el reporte JSON en backend/reports/benchmark_latest.json
(o en --output). Con la misma semilla, los datos sinteticos son identicos en cualquier maquina;
los tiempos cambian con el hardware, por eso el reporte guarda los metadatos del entorno.
"""
from __future__ import annotations

import argparse
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.services import benchmark_service as bench  # noqa: E402

CLI_MAX_SIZE = 20000


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Benchmarks O(n), O(n^2) y O(n log n) de FerrePro")
    parser.add_argument("--source", choices=("synthetic", "real"), default="synthetic")
    parser.add_argument("--sizes", type=int, nargs="+", default=list(bench.DEFAULT_SIZES))
    parser.add_argument("--repetitions", type=int, default=5, choices=range(3, 11), metavar="3..10")
    parser.add_argument("--seed", type=int, default=bench.DEFAULT_SEED)
    parser.add_argument("--search-id", type=int, default=None, help="ID de pedido para la busqueda lineal")
    parser.add_argument("--output", default=None, help="Ruta del reporte JSON")
    parser.add_argument("--no-db", action="store_true", help="No leer la base (sin resultados reales)")
    args = parser.parse_args(argv)
    bad = [n for n in args.sizes if not bench.MIN_SIZE <= n <= CLI_MAX_SIZE]
    if bad:
        parser.error(f"Tamanos fuera de rango ({bench.MIN_SIZE}..{CLI_MAX_SIZE}): {bad}")
    return args


def load_real(source):
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            return bench.load_real_data()
    except Exception as error:  # noqa: BLE001  (sin base se puede medir igual con datos sinteticos)
        print(f"Aviso: no se pudieron leer los datos reales ({type(error).__name__}: {error}).")
        if source == "real":
            sys.exit(1)
        return None


def print_report(report):
    meta, timing = report["meta"], report["timing"]
    print()
    print(f"FerrePro | Benchmarks Fase 2 | {meta['run_at']}")
    print(f"Python {meta['python']} ({meta['implementation']}) | {meta['os']} | {meta['cpu_count']} CPU")
    print(f"Fuente: {meta['source']} | semilla {meta['seed']} | {meta['repetitions']} repeticiones | "
          f"tiempos = mediana en ms (time.perf_counter)")
    if timing["db_fetch_ms"] is not None:
        print(f"Lectura de la base: {timing['db_fetch_ms']} ms (medida aparte del computo)")
    print()
    header = f"{'N':>6} | {'Insertion':>11} | {'Merge':>9} | {'Mejora':>7} | {'Rank O(n^2)':>11} | {'Rank opt':>9} | {'Mejora':>7}"
    print(header)
    print("-" * len(header))
    by_n = {}
    for row in report["comparison"]:
        by_n.setdefault(row["n"], []).append(row)
    for n, (sort_row, rank_row) in by_n.items():
        print(f"{n:>6} | {sort_row['before']['median_ms']:>11.3f} | {sort_row['after']['median_ms']:>9.3f} | "
              f"{str(sort_row['speedup']) + 'x':>7} | {rank_row['before']['median_ms']:>11.3f} | "
              f"{rank_row['after']['median_ms']:>9.3f} | {str(rank_row['speedup']) + 'x':>7}")
    print()
    o_n = report["series"]["o_n"]
    print("O(n) (mediana en ms): " + "; ".join(
        f"N={n}: busqueda {o_n['linear_search'][i]}, suma {o_n['sum_sales'][i]}, conteo {o_n['count_by_customer'][i]}"
        for i, n in enumerate(report["series"]["labels"])))
    eq = report["equivalence"]
    print(f"Equivalencia: orden por fecha {'OK' if eq['sort_by_date'] else 'FALLA'}, "
          f"ranking {'OK' if eq['top_products'] else 'FALLA'} en N = {eq['checked_sizes']}")
    results = report["results"]
    if results:
        print(f"Datos reales: {results['orders_count']} pedidos, ventas confirmadas {results['total_sales']} COP, "
              f"{results['customers_count']} clientes")
        for i, product in enumerate(results["top_products"], 1):
            print(f"  {i}. {product['name']}: {product['units']} u.")
    print(f"Reporte: {meta.get('report_file') or 'solo en memoria (no se pudo escribir el archivo)'}")


def main(argv=None):
    args = parse_args(argv)
    real = None if args.no_db else load_real(args.source)
    report = bench.run_benchmark(args.source, args.sizes, args.repetitions, args.seed, real=real,
                                 search_id=args.search_id, report_path=args.output)
    print_report(report)
    return report


if __name__ == "__main__":
    main()
