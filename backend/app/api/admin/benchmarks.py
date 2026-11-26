"""Benchmarks de la Fase 2. Solo admin: el guardia de admin_bp devuelve 401 sin sesion y 403 sin rol.

Tope de carga: el costo de Insertion Sort crece con n^2, asi que se limita la suma de n^2 por
repeticion. Con el tope, el peor caso permitido (los 5 tamanos por defecto con 5 repeticiones)
tarda unos 18 s en una laptop modesta, por debajo del timeout de 30 s de gunicorn.
"""
from flask import current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.api.admin import admin_bp
from app.extensions import db
from app.services import benchmark_service as bench
from app.utils.http import json_error, no_store
from app.utils.validation import ValidationError, Validator

SOURCES = ("synthetic", "real")
MAX_WORK = sum(n * n for n in bench.DEFAULT_SIZES) * bench.MAX_REPETITIONS  # sum(n^2) * repeticiones


def _sizes(raw, errors):
    if raw is None:
        return list(bench.DEFAULT_SIZES)
    if not isinstance(raw, list) or not 1 <= len(raw) <= bench.MAX_SIZES:
        errors["sizes"] = f"Envía entre 1 y {bench.MAX_SIZES} tamaños."
        return []
    sizes = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int) or not bench.MIN_SIZE <= value <= bench.MAX_SIZE:
            errors["sizes"] = f"Cada tamaño debe ser un entero entre {bench.MIN_SIZE} y {bench.MAX_SIZE}."
            return []
        if value not in sizes:
            sizes.append(value)
    # Orden ascendente con el merge sort propio (los tamanos alimentan la serie del grafico)
    from app.services.algorithms_service import merge_sort
    return merge_sort(sizes)


@admin_bp.post("/benchmarks/run")
def run_benchmark():
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    v = Validator(data)
    source = v.choice("source", SOURCES, required=False, default="synthetic")
    repetitions = v.integer("repetitions", bench.MIN_REPETITIONS, bench.MAX_REPETITIONS,
                            required=False, default=bench.DEFAULT_REPETITIONS)
    seed = v.integer("seed", 0, 2_147_483_647, required=False, default=bench.DEFAULT_SEED)
    search_id = v.integer("search_id", 1, 2_147_483_647, required=False, default=None)
    sizes = _sizes(data.get("sizes"), v.errors)
    v.raise_if_errors()
    if source == "synthetic" and sum(n * n for n in sizes) * repetitions > MAX_WORK:
        raise ValidationError({"sizes": "La combinación de tamaños y repeticiones excede el tope seguro. "
                                        "Reduce los tamaños o las repeticiones."})

    try:
        real = bench.load_real_data()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning("Benchmark: no se pudieron leer los datos reales.")
        if source == "real":
            return json_error(503, "database_unavailable", "No se pudo leer la base de datos.")
        real = None
    if source == "real" and real is not None and len(real.orders) > bench.MAX_SIZE:
        real.orders = real.orders[:bench.MAX_SIZE]  # tope tambien en modo real
        real.notes.append(f"Se midieron los primeros {bench.MAX_SIZE} pedidos.")

    try:
        report = bench.run_benchmark(source, sizes, repetitions, seed, real=real, search_id=search_id)
    except bench.BenchmarkBusy as error:
        return json_error(409, "benchmark_running", str(error))
    if real is not None and real.notes:
        report["meta"]["notes"] = real.notes
    return no_store(jsonify(report))


@admin_bp.get("/benchmarks/latest")
def latest_benchmark():
    report = bench.load_latest()
    if report is None:
        return json_error(404, "no_benchmark", "Todavía no se ha ejecutado ningún benchmark.")
    return no_store(jsonify(report))
