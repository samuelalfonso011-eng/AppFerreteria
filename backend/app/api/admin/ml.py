import importlib.util
import math

from flask import current_app, jsonify, request

from app.api.admin import admin_bp
from app.ml import data_pipeline as pipeline, inference_service as inference
from app.ml.train_models import start_training, train, training_state
from app.services.errors import BusinessError
from app.utils.validation import ValidationError, Validator


def ml_available():
    """TensorFlow no cabe en una función serverless (Vercel limita el paquete a 250 MB).

    Sin TensorFlow la app funciona igual; solo entrenar y predecir responden 503 con un motivo claro,
    en vez de un 500 por ImportError. El backend en Docker sí incluye TensorFlow.
    """
    return importlib.util.find_spec("tensorflow") is not None


def require_ml():
    if not ml_available():
        raise BusinessError("Los modelos de IA no están disponibles en este despliegue. Usa el backend con "
                            "TensorFlow (Docker) para entrenar y predecir.", code="ml_unavailable", status=503)


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"body": "Envía un objeto JSON."})
    return data


@admin_bp.post("/ml/train")
def train_models():
    v = Validator(payload())
    seed = v.integer("seed", 0, 2_147_483_647, required=False, default=42)
    v.raise_if_errors()
    require_ml()
    if current_app.config["ML_TRAIN_ASYNC"]:
        return jsonify(training=start_training(seed)), 202
    return jsonify(runs=train(seed)), 201


@admin_bp.get("/ml/status")
def model_status():
    return jsonify(models=inference.status(), training=training_state(), available=ml_available())


def transaction(raw):
    if not isinstance(raw, dict):
        raise ValidationError({"transaction": "Se requiere un objeto."})
    v = Validator(raw)
    source = {
        "channel": v.choice("channel", pipeline.ORDER_CHANNELS),
        "payment_method": v.choice("payment_method", pipeline.PAYMENT_METHODS, required=False),
        "prior_frequency": v.integer("prior_frequency", 0, 10_000_000, required=False, default=0),
    }
    try:
        source["occurred_at"] = pipeline.iso(pipeline.timestamp(raw.get("occurred_at", "")))
    except (AttributeError, ValueError, OverflowError):
        v.error("occurred_at", "Usa una fecha ISO 8601 con zona horaria.")
    for key, high in (("amount", 1e12), ("discount_pct", 100), ("cancellation_rate", 1)):
        val = raw.get(key, None if key == "amount" else 0)
        try:
            number = float(val)
            if isinstance(val, bool) or not math.isfinite(number) or not 0 <= number <= high:
                raise ValueError
            source[key] = number
        except (TypeError, ValueError, OverflowError):
            v.error(key, "Valor numérico fuera de rango.")
    valid = raw.get("hash_valid")
    if valid is not None and (type(valid) is not int or valid not in (0, 1)):
        v.error("hash_valid", "Usa 0, 1 o null.")
    source["hash_valid"] = valid
    v.raise_if_errors()
    return source


@admin_bp.post("/ml/predict/fraud")
def predict_fraud():
    require_ml()
    raw = payload()
    modes = [key for key in ("order_id", "invoice_id", "payment_id", "transaction") if key in raw]
    if len(modes) != 1:
        raise ValidationError({"body": "Indica una sola referencia o una transacción."})
    mode = modes[0]
    if mode == "transaction":
        snapshot = transaction(raw[mode])
    else:
        v = Validator(raw)
        entity_id = v.integer(mode, 1, 2_147_483_647)
        v.raise_if_errors()
        snapshot = pipeline.operation(mode, entity_id)
    return jsonify(inference.predict_fraud(snapshot)), 201


@admin_bp.get("/ml/predict/demand")
def predict_demand():
    require_ml()
    v = Validator(request.args.to_dict())
    horizon = v.integer("horizon", 1, 30, required=False, default=7)
    pid = v.integer("product_id", -2_147_483_648, 2_147_483_647, required=False)
    v.raise_if_errors()
    return jsonify(inference.predict_demand(pid, horizon))
