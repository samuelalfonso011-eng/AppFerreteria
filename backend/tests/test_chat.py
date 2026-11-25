import io
import json
from urllib.error import HTTPError, URLError

import pytest

from app.extensions import db
from app.models import Product
from app.services import chat_service


def test_fallback_reuses_catalog_and_tracks_inventory(api, app, monkeypatch):
    app.config["GEMINI_API_KEY"] = ""
    featured = api.get("/api/catalog/products").get_json()["products"][0]
    from app.api import public
    with monkeypatch.context() as warm:
        warm.setattr(public, "build_products", lambda: pytest.fail("El catálogo ya está en caché"))
        result = api.post("/api/chat", {"message": featured["sku"]}).get_json()
    assert result["mode"] == "fallback"
    assert result["suggested_products"][0]["id"] == featured["id"]
    assert result["suggested_products"][0]["stock"] == featured["stock"]

    product = db.session.get(Product, featured["id"])
    product.stock = 0
    db.session.commit()
    result = api.post("/api/chat", {"message": featured["sku"]}).get_json()
    assert result["suggested_products"][0]["stock"] == 0
    assert "stock disponible: 0" in result["reply"]

    product = db.session.get(Product, featured["id"])
    product.is_active = False
    db.session.commit()
    result = api.post("/api/chat", {"message": featured["sku"]}).get_json()
    assert featured["id"] not in {p["id"] for p in result["suggested_products"]}
    assert not api.post("/api/chat", {"message": "hiperdesconocido"}).get_json()["suggested_products"]
    assert "categorías" in api.post("/api/chat", {"message": "hiperdesconocido"}).get_json()["reply"]
    assert "garantía legal" in api.post("/api/chat", {"message": "¿Qué garantía tienen?"}).get_json()["reply"]


def test_ai_uses_only_catalog_facts_and_last_six_messages(api, app, monkeypatch):
    app.config.update(GEMINI_API_KEY="test-key", GEMINI_MODEL="gemini-2.5-flash")
    product = api.get("/api/catalog/products").get_json()["products"][0]

    def generate(request, timeout):
        assert request.get_header("X-goog-api-key") == "test-key"
        assert "test-key" not in request.full_url
        assert timeout == 5
        sent = json.loads(request.data)
        assert "exclusivamente" in sent["systemInstruction"]["parts"][0]["text"]
        context = json.loads(sent["contents"][0]["parts"][0]["text"])
        assert [x["content"] for x in context["historial"]] == [f"Turno {i}" for i in range(2, 8)]
        assert any(p["id"] == product["id"] for p in context["catalogo"])
        output = json.dumps({"product_ids": [product["id"]], "policy": "", "reply": "Precio inventado"})
        return io.BytesIO(json.dumps({
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": output}]}}],
        }).encode())

    monkeypatch.setattr(chat_service, "urlopen", generate)
    history = [{"role": "user", "content": f"Turno {i}"} for i in range(8)]
    response = api.post("/api/chat", {"message": product["name"], "history": history})
    assert response.status_code == 200
    result = response.get_json()
    assert result["mode"] == "ai"
    assert result["suggested_products"][0]["price"] == product["price"]
    assert "inventado" not in result["reply"]


@pytest.mark.parametrize("error", [HTTPError("test", 429, "quota", {}, None), URLError("offline"), TimeoutError()])
def test_provider_errors_use_fallback(api, app, monkeypatch, error):
    app.config["GEMINI_API_KEY"] = "test-key"

    def unavailable(*args, **kwargs):
        raise error

    monkeypatch.setattr(chat_service, "urlopen", unavailable)
    result = api.post("/api/chat", {"message": "taladro"})
    assert result.status_code == 200
    assert result.get_json()["mode"] == "fallback"


def test_validation_and_rate_limit(api, app):
    app.config["GEMINI_API_KEY"] = ""
    assert api.post("/api/chat", {"message": "   "}).status_code == 400
    assert api.post("/api/chat", {"message": "a" * 501}).status_code == 400
    assert api.post("/api/chat", {"message": "a", "history": {}}).status_code == 400
    assert api.post("/api/chat", {"message": "a"}, csrf=False).status_code == 403
    for _ in range(7):
        assert api.post("/api/chat", {"message": "herramientas"}).status_code == 200
    blocked = api.post("/api/chat", {"message": "herramientas"})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
