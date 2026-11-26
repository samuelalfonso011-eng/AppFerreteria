"""Entrenamiento reproducible y publicación atómica de la pareja de modelos."""

import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from uuid import uuid4

from flask import current_app
from sqlalchemy import text

from app.extensions import db
from app.ml import data_pipeline as pipeline
from app.models.ml import ModelRun
from app.services.errors import BusinessError
from app.services.statistics_service import fit

TRAIN_LOCK = Lock()
FRAUD = "fraud_classifier"
DEMAND = "demand_regressor"
FEATURES = [
    "log_amount",
    "log_prior_frequency",
    "discount_fraction",
    "cancellation_rate",
    "hash_invalid",
    "hash_unknown",
    "hour_sin",
    "hour_cos",
    *pipeline.PAYMENT_METHODS,
    *pipeline.ORDER_CHANNELS,
]
DEMAND_FEATURES = ["lag_1", "rolling_mean_7", "period_index", "weekday_sin", "weekday_cos", "log_lead_days"]
# Anticipaciones de entrenamiento: todas las que se evalúan y se pronostican (horizonte máximo de la API: 30).
# Antes solo 1, 2, 7, 14 y 30: el tramo de prueba pedía anticipaciones que el modelo nunca vio.
DEMAND_LEADS = range(1, 31)
# Señales agrupadas para la explicación: una variable categórica o cíclica se mueve como bloque.
SIGNAL_GROUPS = {
    "hour": ("hour_sin", "hour_cos"),
    "hash_state": ("hash_invalid", "hash_unknown"),
    "payment_method": tuple(pipeline.PAYMENT_METHODS),
    "channel": tuple(pipeline.ORDER_CHANNELS),
}


def artifact_root():
    return Path(current_app.config["ML_ARTIFACT_DIR"]).resolve()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def network(x, binary, targets=None):
    import tensorflow as tf

    normalizer = tf.keras.layers.Normalization(name="training_normalization")
    normalizer.adapt(x)
    layers = [tf.keras.Input(shape=(x.shape[1],)), normalizer, tf.keras.layers.Dense(24, activation="relu")]
    if binary:
        layers.append(tf.keras.layers.Dropout(0.15))
    layers.extend(
        [
            tf.keras.layers.Dense(12, activation="relu"),
            tf.keras.layers.Dense(1, activation="sigmoid" if binary else "linear"),
        ]
    )
    if targets is not None:
        # El modelo guardado devuelve unidades. Inicializar la salida cerca de la media de train.
        layers.append(tf.keras.layers.Rescaling(max(float(targets.std()), 1.0), offset=float(targets.mean())))
    model = tf.keras.Sequential(layers)
    model.compile(optimizer=tf.keras.optimizers.Adam(0.008), loss="binary_crossentropy" if binary else "mse")
    return model


def optimize(model, x, y, seed, epochs):
    import numpy as np

    rng = np.random.default_rng(seed)
    for _ in range(epochs):
        order = rng.permutation(len(x))
        for start in range(0, len(order), 32):
            batch = order[start : start + 32]
            model.train_on_batch(x[batch], y[batch])


def classification(labels, probabilities):
    counts = Counter()
    for y, probability in zip(labels, probabilities, strict=True):
        positive = probability >= 0.5
        counts["tp" if y and positive else "fn" if y else "fp" if positive else "tn"] += 1
    tp, fp, fn = (counts[k] for k in ("tp", "fp", "fn"))
    return dict(
        precision=tp / (tp + fp) if tp + fp else 0,
        recall=tp / (tp + fn) if tp + fn else 0,
        f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
        confusion_matrix={k: counts[k] for k in ("tp", "fp", "tn", "fn")},
    )


def classifier(seed, epochs):
    import numpy as np

    train, test, summary = pipeline.fraud_dataset(seed)
    for key, rows in (("train", train), ("test", test)):
        counts = Counter(row[2] for row in rows)
        summary[key] = dict(
            size=len(rows),
            fraud_fraction=counts[1] / len(rows),
            normal=counts[0],
            fraudulenta=counts[1],
            label_sources=dict(Counter(row[3] for row in rows)),
            first=pipeline.iso(rows[0][0]),
            last=pipeline.iso(rows[-1][0]),
        )
    x = np.asarray([r[1] for r in train], dtype="float32")
    y = np.asarray([r[2] for r in train], dtype="float32")
    model = network(x, True)
    counts = np.bincount(y.astype(int), minlength=2)
    extra = int(max(counts) - min(counts))
    indices = np.random.default_rng(seed).choice(np.flatnonzero(y == np.argmin(counts)), extra)
    optimize(model, np.concatenate([x, x[indices]]), np.concatenate([y, y[indices]]), seed, epochs)
    summary["oversampled_train_rows"] = extra
    probabilities = model(np.asarray([r[1] for r in test], dtype="float32"), training=False).numpy().ravel()
    metrics = classification([r[2] for r in test], probabilities)
    metrics["by_label_source"] = {}
    for source in ("real", "simulated"):
        group = [(row[2], p) for row, p in zip(test, probabilities) if row[3] == source]
        metrics["by_label_source"][source] = classification(*zip(*group)) if group else None
    return model, summary, metrics, {"features": FEATURES, "training_mean": x.mean(axis=0).tolist()}


def rollout(model, start, history, horizon):
    import numpy as np

    # Pronóstico directo desde un único origen: ninguna predicción alimenta la siguiente.
    x = [
        pipeline.demand_vector(start + timedelta(days=len(history) + lead - 1), history, lead)
        for lead in range(1, horizon + 1)
    ]
    predictions = model(np.asarray(x, dtype="float32"), training=False).numpy().ravel()
    return [max(0.0, float(value)) for value in predictions]


def errors(actual, predicted):
    import numpy as np

    actual = np.asarray(actual, dtype="float64")
    diff = actual - predicted
    ss = float(np.sum((actual - actual.mean()) ** 2))
    return dict(
        mae=float(np.abs(diff).mean()),
        rmse=float(np.sqrt(np.mean(diff**2))),
        r2=1 - float(np.sum(diff**2)) / ss if ss else None,
    )


def regressor(seed, epochs):
    import numpy as np

    series, cutoff, summary = pipeline.demand_dataset(seed)
    x, y = [], []
    for product in series.values():
        start = date.fromisoformat(product["start"])
        history = product["values"]
        split = (cutoff - start).days
        product["split"] = split
        for i in range(1, split):
            for lead in DEMAND_LEADS:
                known = i - lead + 1
                if known > 0:
                    x.append(pipeline.demand_vector(start + timedelta(days=i), history, lead, known))
                    y.append(history[i])
    x = np.asarray(x, dtype="float32")
    y = np.asarray(y, dtype="float32")
    model = network(x, False, y)
    optimize(model, x, y, seed, epochs)
    observed, keras, baseline = [], [], []
    for product in series.values():
        values, split = product["values"], product["split"]
        m, b = fit(values[:split])
        product["baseline"] = [m, b]
        forecasts = rollout(model, date.fromisoformat(product["start"]), values[:split], len(values) - split)
        product["holdout_keras"] = forecasts
        observed.extend(values[split:])
        keras.extend(forecasts)
        baseline.extend(b + m * i for i in range(split, len(values)))
    summary.update(
        train_size=sum(p["split"] - 1 for p in series.values()),
        training_examples=len(y),
        test_size=len(observed),
        products=len(series),
    )
    return (
        model,
        summary,
        {"keras": errors(observed, keras), "linear_phase4": errors(observed, baseline)},
        {"features": DEMAND_FEATURES, "products": series},
    )


def train(seed=42):
    """Entrenamiento síncrono (CLI y pruebas). La API usa start_training() en segundo plano."""
    if not TRAIN_LOCK.acquire(blocking=False):
        raise BusinessError("Ya hay un entrenamiento en curso.", code="training_busy")
    try:
        return _train_locked(seed)
    finally:
        TRAIN_LOCK.release()


# ---------------------------------------------------------------------------
# Entrenamiento en segundo plano. TensorFlow tarda más que el timeout de gunicorn (30 s),
# así que la petición solo lo inicia (202) y el panel consulta GET /ml/status.
# El estado vive en ML_ARTIFACT_DIR/training.json: el volumen ya es compartido entre workers.
# ---------------------------------------------------------------------------
STATE_FILE = "training.json"


def _state_path():
    return artifact_root() / STATE_FILE


def _write_state(state):
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{STATE_FILE}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)  # reemplazo atómico: nunca se lee un JSON a medias


def training_state():
    """Último trabajo de entrenamiento o None. Un trabajo colgado (proceso caído) se informa como fallido."""
    from app.utils.timeutils import utcnow

    try:
        state = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if state.get("state") == "running":
        from datetime import datetime

        started = datetime.fromisoformat(state["started_at"].replace("Z", "+00:00"))
        if (utcnow() - started).total_seconds() > current_app.config["ML_TRAIN_STALE_SECONDS"]:
            state.update(state="failed", error="training_stalled",
                         message="El entrenamiento no terminó. Vuelve a iniciarlo.")
    return state


def start_training(seed=42):
    """Inicia el entrenamiento en un hilo y devuelve el estado inicial. 409 si ya hay uno en curso."""
    import threading

    from app.utils.timeutils import iso, utcnow

    current = training_state()
    if current and current.get("state") == "running":
        raise BusinessError("Ya hay un entrenamiento en curso.", code="training_busy")
    if not TRAIN_LOCK.acquire(blocking=False):
        raise BusinessError("Ya hay un entrenamiento en curso.", code="training_busy")
    app = current_app._get_current_object()
    state = {"state": "running", "seed": seed, "started_at": iso(utcnow()), "finished_at": None,
             "version": None, "error": None, "message": None}
    try:
        _write_state(state)
    except OSError as exc:
        TRAIN_LOCK.release()
        raise BusinessError("No se pudo escribir en el directorio de artefactos.",
                            code="artifact_unavailable", status=503) from exc

    def job():
        result = dict(state)
        try:
            with app.app_context():
                try:
                    runs = _train_locked(seed)
                    result.update(state="succeeded", version=runs[0]["version"])
                except BusinessError as exc:
                    if exc.code == "training_busy":
                        return  # otro worker tiene el trabajo y su estado: no sobrescribirlo
                    result.update(state="failed", error=exc.code, message=exc.message)
                except Exception:  # noqa: BLE001  (el hilo no tiene a quién propagar el error)
                    app.logger.exception("Fallo el entrenamiento en segundo plano")
                    result.update(state="failed", error="server_error",
                                  message="El entrenamiento falló. Revisa los registros del servidor.")
                finally:
                    db.session.remove()
                result["finished_at"] = iso(utcnow())
                _write_state(result)
        finally:
            TRAIN_LOCK.release()

    threading.Thread(target=job, name="ferrepro-ml-training", daemon=True).start()
    return state


def _train_locked(seed):
    """Cuerpo del entrenamiento. El llamador ya tiene TRAIN_LOCK."""
    try:
        if db.session.get_bind().dialect.name == "postgresql":
            if not db.session.scalar(text("select pg_try_advisory_xact_lock(617203583)")):
                raise BusinessError("Ya hay un entrenamiento en curso.", code="training_busy")
        import tensorflow as tf

        tf.config.experimental.enable_op_determinism()
        version = uuid4().hex
        root = artifact_root()
        root.mkdir(parents=True, exist_ok=True)
        runs = []
        with TemporaryDirectory(dir=root, prefix=".training-") as temporary:
            folder = Path(temporary)
            for name, trainer in ((FRAUD, classifier), (DEMAND, regressor)):
                tf.keras.utils.set_random_seed(seed)
                epochs = current_app.config["ML_EPOCHS"]
                model, summary, metrics, meta = trainer(seed, epochs)
                path = folder / (name + ".keras")
                model.save(path)
                meta_path = path.with_suffix(".json")
                meta_path.write_text(json.dumps(meta, ensure_ascii=False, allow_nan=False), encoding="utf-8")
                summary.update(
                    epochs=epochs,
                    tensorflow=tf.__version__,
                    keras=tf.keras.__version__,
                    artifact_sha256=sha(path),
                    metadata_sha256=sha(meta_path),
                )
                run = ModelRun(
                    model_name=name,
                    version=version,
                    artifact_path=f"{version}/{path.name}",
                    seed=seed,
                    dataset_summary=summary,
                    metrics=metrics,
                )
                db.session.add(run)
                runs.append(run)
            folder.rename(root / version)
        try:
            db.session.commit()
        except Exception:
            # Sin la fila de versión los archivos publicados quedarían huérfanos: se retiran.
            import shutil

            shutil.rmtree(root / version, ignore_errors=True)
            raise
        return [run.summary() for run in runs]
    except OSError as exc:
        db.session.rollback()
        raise BusinessError(
            "No se pudieron publicar los modelos en el directorio de artefactos.",
            code="artifact_unavailable",
            status=503,
        ) from exc
    except Exception:
        db.session.rollback()
        raise
