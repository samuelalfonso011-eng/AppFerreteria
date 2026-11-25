from flask import current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.api import api_bp
from app.extensions import db
from app.services import chat_service
from app.utils.http import json_error, no_store
from app.utils.security import client_ip, limiter


@api_bp.post("/chat")
def chat():
    allowed, retry = limiter("chat").hit(client_ip())
    if not allowed:
        response = json_error(429, "rate_limited", "Enviaste demasiados mensajes. Espera un momento.",
                              retry_after=retry)
        response.headers["Retry-After"] = str(retry)
        return response

    try:
        message, history = chat_service.validate_request(request.get_json(silent=True))
    except ValueError as error:
        return json_error(400, "validation", str(error))

    try:
        products, categories, policies = chat_service.load_context()
    except SQLAlchemyError:
        current_app.logger.warning("No fue posible leer el catálogo para el chat.")
        products, categories, policies = [], [], {}
    finally:
        db.session.remove()

    return no_store(jsonify(chat_service.answer(message, history, products, categories, policies)))
