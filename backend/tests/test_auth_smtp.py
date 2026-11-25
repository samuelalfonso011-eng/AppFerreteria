"""Prueba de integración con entrega SMTP por TCP y PostgreSQL opcional."""

import os
import socket
from email import policy
from email.parser import BytesParser
from queue import Queue
from uuid import uuid4

import pytest
from aiosmtpd.controller import Controller
from sqlalchemy import text

from app import create_app
from app.config import TestingConfig, normalize_db_url
from app.extensions import db
from app.models import User
from tests.conftest import ApiClient
from tests.test_auth import GOOD_PASSWORD, link_token, register_payload


@pytest.fixture
def smtp_server():
    messages = Queue()

    class Inbox:
        async def handle_DATA(self, server, session, envelope):
            messages.put(BytesParser(policy=policy.default).parsebytes(envelope.content))
            return "250 Accepted"

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    controller = Controller(Inbox(), hostname="127.0.0.1", port=port)
    controller.start()
    try:
        yield port, messages
    finally:
        controller.stop()


@pytest.fixture
def integration_app(app, monkeypatch):
    url = os.environ.get("FERREPRO_TEST_POSTGRES_URL")
    if not url:
        yield app
        return
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", normalize_db_url(url))
    monkeypatch.setattr(TestingConfig, "AUTO_CREATE_DB", False)
    instance = create_app("testing")
    with instance.app_context():
        yield instance
        db.session.remove()
        db.engine.dispose()


def test_registration_smtp_and_roles(integration_app, smtp_server):
    port, messages = smtp_server
    app = integration_app
    app.config.update(TEST_REAL_SMTP=True, SMTP_HOST="127.0.0.1", SMTP_PORT=port,
                      SMTP_FROM="tienda@example.com", SMTP_USER="", SMTP_PASSWORD="",
                      SMTP_SSL=False, SMTP_STARTTLS=False)
    email = f"cliente-{uuid4().hex}@example.com"
    admin_email = f"admin-{uuid4().hex}@example.com"
    admin = User(email=admin_email, full_name="Admin Integración", role=User.ROLE_ADMIN)
    admin.set_password(GOOD_PASSWORD)
    db.session.add(admin)
    db.session.commit()
    customer = ApiClient(app.test_client())

    payload = register_payload(email=f"  {email.upper()}  ")
    assert customer.post("/api/auth/register", payload).status_code == 202
    first_message = messages.get(timeout=5)
    assert first_message["To"] == email
    assert customer.post("/api/auth/register", register_payload(email=email)).status_code == 409
    assert messages.empty()

    if db.engine.dialect.name == "postgresql":
        assert set(db.session.execute(text("""
            select consent_type from public.legal_consents
            where user_id = (select id from public.users where email = :email)
        """), {"email": email}).scalars()) == {"terms", "habeas_data"}
    assert customer.login(email, GOOD_PASSWORD).status_code == 401
    assert customer.post("/api/auth/activation/resend", {"email": email}).status_code == 202
    message = messages.get(timeout=5)
    assert message["To"] == email
    token = link_token({"body": message.get_content()}, "activar")
    assert customer.post("/api/auth/activate", {"token": token}).get_json()["user"]["role"] == "customer"
    assert customer.post("/api/auth/activate", {"token": token}).status_code == 400
    assert customer.get("/api/admin/dashboard").status_code == 403
    assert customer.post("/api/auth/logout").status_code == 200
    assert customer.get("/api/auth/me").get_json()["user"] is None
    assert customer.login(email, "ContraseñaIncorrecta12").status_code == 401
    response = customer.login(email.upper(), GOOD_PASSWORD)
    assert response.status_code == 200
    assert response.get_json()["user"]["role"] == "customer"
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]

    admin_api = ApiClient(app.test_client())
    assert admin_api.login(admin_email, GOOD_PASSWORD).get_json()["user"]["role"] == "admin"
    assert admin_api.get("/api/admin/dashboard").status_code == 200
    assert admin_api.post("/api/auth/logout").status_code == 200
    assert admin_api.get("/api/admin/dashboard").status_code == 401
