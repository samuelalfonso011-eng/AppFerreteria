"""Carga por aplicación y versión, sin entrenamiento en las rutas de lectura."""

import json
from datetime import date, timedelta
from threading import Lock

from flask import current_app

from app.extensions import db
from app.ml import data_pipeline as pipeline
from app.ml.train_models import artifact_root, DEMAND, FRAUD, rollout, sha
from app.models.ml import FraudPrediction, ModelRun
from app.services.errors import BusinessError

LOAD_LOCK = Lock()


def latest(name):
    return ModelRun.query.filter_by(model_name=name).order_by(ModelRun.id.desc()).first()


def location(run):
    root = artifact_root()
    path = (root / run.artifact_path).resolve()
    if root not in path.parents or path.suffix != ".keras":
        raise BusinessError("Referencia de artefacto inválida.", code="artifact_unavailable", status=503)
    return path


def load(name):
    run = latest(name)
    if not run:
        raise BusinessError("Primero entrena los modelos.", code="model_not_trained")
    with LOAD_LOCK:
        cache = current_app.extensions.setdefault("ml_models", {})
        entry = cache.get(name)
        if not entry or entry[0] != run.version:
            import tensorflow as tf

            path = location(run)
            metadata = path.with_suffix(".json")
            try:
                if (
                    sha(path) != run.dataset_summary["artifact_sha256"]
                    or sha(metadata) != run.dataset_summary["metadata_sha256"]
                ):
                    raise ValueError("checksum")
                model = tf.keras.models.load_model(path, compile=False, safe_mode=True)
                entry = (run.version, model, json.loads(metadata.read_text(encoding="utf-8")))
            except (OSError, ValueError, KeyError) as exc:
                raise BusinessError(
                    "Artefactos ausentes o dañados.", code="artifact_unavailable", status=503
                ) from exc
            cache[name] = entry
    return run, entry[1], entry[2]


def status():
    models = {}
    for name in (FRAUD, DEMAND):
        run = latest(name)
        item = current_app.extensions.get("ml_models", {}).get(name)
        models[name] = dict(
            run=run.summary() if run else None,
            on_disk=bool(run and location(run).is_file() and location(run).with_suffix(".json").is_file()),
            loaded=bool(run and item and item[0] == run.version),
        )
    return models


def predict_fraud(snapshot):
    import numpy as np

    run, model, meta = load(FRAUD)
    x = np.asarray(pipeline.fraud_vector(snapshot), dtype="float32")
    # Sensibilidad local: sustituir una característica cada vez por su media de entrenamiento.
    batch = np.tile(x, (len(x) + 1, 1))
    for i, mean in enumerate(meta["training_mean"]):
        batch[i + 1, i] = mean
    probabilities = model(batch, training=False).numpy().ravel()
    probability = float(probabilities[0])
    effects = sorted(
        ((name, probability - float(p)) for name, p in zip(meta["features"], probabilities[1:])),
        key=lambda pair: abs(pair[1]),
        reverse=True,
    )
    row = FraudPrediction(
        order_id=snapshot.get("order_id"),
        invoice_id=snapshot.get("invoice_id"),
        payment_id=snapshot.get("payment_id"),
        model_run_id=run.id,
        fraud_probability=probability,
        predicted_label="fraudulenta" if probability >= 0.5 else "normal",
        feature_snapshot=snapshot,
    )
    db.session.add(row)
    db.session.commit()
    return dict(
        id=row.id,
        model_run_id=run.id,
        version=run.version,
        fraud_probability=probability,
        predicted_label=row.predicted_label,
        signals=[dict(feature=f, delta_probability=d) for f, d in effects[:3]],
    )


def predict_demand(product_id, horizon):
    run, model, meta = load(DEMAND)
    series = meta["products"]
    if product_id is not None and str(product_id) not in series:
        raise BusinessError("Producto ausente de esta corrida.", code="not_found", status=404)
    products = []
    for pid, product in series.items():
        if product_id is not None and int(pid) != product_id:
            continue
        start = date.fromisoformat(product["start"])
        values, split = product["values"], product["split"]
        m, b = product["baseline"]

        def point(i, observed, prediction):
            return dict(
                period=(start + timedelta(days=i)).isoformat(),
                observed=observed,
                keras=prediction,
                linear_phase4=m * i + b,
            )

        historical = [point(i, values[i], p) for i, p in enumerate(product["holdout_keras"], split)]
        future = [
            point(i, None, p) for i, p in enumerate(rollout(model, start, values, horizon), len(values))
        ]
        products.append(dict(product_id=int(pid), name=product["name"], test=historical, forecast=future))
    return dict(
        model_run_id=run.id,
        version=run.version,
        source=run.dataset_summary["source"],
        cutoff=run.dataset_summary["cutoff"],
        metrics=run.metrics,
        products=products,
    )
