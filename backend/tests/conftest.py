import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.cli import seed_demo_data  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402

ADMIN_PASSWORD = "AdminSegura2026"
CUSTOMER_PASSWORD = "ClienteSeguro2026"


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        seed_demo_data()
        admin = User(email="admin@ferrepro.test", full_name="Admin Prueba", role=User.ROLE_ADMIN)
        admin.set_password(ADMIN_PASSWORD)
        customer = User(email="cliente@ferrepro.test", full_name="Cliente Prueba", role=User.ROLE_CUSTOMER)
        customer.set_password(CUSTOMER_PASSWORD)
        db.session.add_all([admin, customer])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


class ApiClient:
    """Cliente que imita al frontend: obtiene el token CSRF y lo envia en cada escritura."""

    def __init__(self, client):
        self.client = client
        self.csrf = None

    def token(self):
        if self.csrf is None:
            self.csrf = self.client.get("/api/auth/csrf").get_json()["csrf"]
        return self.csrf

    def get(self, path, **kw):
        return self.client.get(path, **kw)

    def send(self, method, path, json=None, csrf=True):
        headers = {"X-CSRF-Token": self.token()} if csrf else {}
        response = self.client.open(path, method=method, json=json if json is not None else {}, headers=headers)
        # Igual que el frontend: si el servidor rota el token (login, activacion, reset), usar el nuevo
        body = response.get_json(silent=True)
        if isinstance(body, dict) and isinstance(body.get("csrf"), str):
            self.csrf = body["csrf"]
        return response

    def post(self, path, json=None, **kw):
        return self.send("POST", path, json, **kw)

    def put(self, path, json=None, **kw):
        return self.send("PUT", path, json, **kw)

    def delete(self, path, **kw):
        return self.send("DELETE", path, None, **kw)

    def login(self, email, password):
        response = self.post("/api/auth/login", {"email": email, "password": password})
        if response.status_code == 200:
            self.csrf = response.get_json()["csrf"]
        return response


@pytest.fixture()
def api(app):
    return ApiClient(app.test_client())


@pytest.fixture()
def admin_api(app):
    client = ApiClient(app.test_client())
    assert client.login("admin@ferrepro.test", ADMIN_PASSWORD).status_code == 200
    return client
