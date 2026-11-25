import re

from app.extensions import db
from app.models import PrivacyConsent, User
from tests.conftest import ADMIN_PASSWORD, ApiClient

GOOD_PASSWORD = "TornilloSeguro2026"


def outbox(app):
    return app.extensions.setdefault("mail_outbox", [])


def link_token(message, kind):
    match = re.search(rf"/#{kind}/(\S+)", message["body"])
    assert match, message["body"]
    return match.group(1)


def register_payload(**overrides):
    payload = {"name": "Andrés Cliente", "email": "andres@example.com", "password": GOOD_PASSWORD,
               "accept_terms": True, "accept_privacy": True}
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------- registro y activacion

def test_register_creates_pending_customer_with_consents(api, app):
    response = api.post("/api/auth/register", register_payload())
    assert response.status_code == 202
    with app.app_context():
        user = User.query.filter_by(email="andres@example.com").one()
        assert user.role == "customer" and not user.is_active
        assert user.password_hash.startswith(("scrypt:", "pbkdf2:")) and GOOD_PASSWORD not in user.password_hash
        consents = PrivacyConsent.query.filter_by(user_id=user.id).all()
        assert {c.document for c in consents} == {"terms", "habeas_data"}
        assert all(c.purpose == "registration" and c.ip_address for c in consents)
    assert outbox(app)[-1]["to"] == "andres@example.com"
    # Sin confirmar el correo no puede entrar, con el mismo mensaje generico
    login = api.login("andres@example.com", GOOD_PASSWORD)
    assert login.status_code == 401 and login.get_json()["message"] == "Correo o contraseña incorrectos."


def test_activation_link_signs_in_and_works_once(api, app):
    api.post("/api/auth/register", register_payload())
    token = link_token(outbox(app)[-1], "activar")
    first = api.post("/api/auth/activate", {"token": token})
    assert first.status_code == 200 and first.get_json()["user"]["role"] == "customer"
    assert api.get("/api/auth/me").get_json()["user"]["email"] == "andres@example.com"
    assert api.post("/api/auth/activate", {"token": token}).status_code == 400


def test_register_returns_conflict_for_normalized_duplicate(api, app):
    assert api.post("/api/auth/register", register_payload()).status_code == 202
    duplicate = api.post("/api/auth/register", register_payload(email="  ANDRES@Example.COM  "))
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"] == "email_taken"
    assert "email" in duplicate.get_json()["fields"]
    assert len(outbox(app)) == 1
    with app.app_context():
        user = User.query.filter_by(email="andres@example.com").one()
        assert PrivacyConsent.query.filter_by(user_id=user.id).count() == 2


def test_resends_pending_activation_and_rejects_expired_link(api, app):
    assert api.post("/api/auth/register", register_payload()).status_code == 202
    token = link_token(outbox(app)[-1], "activar")
    original_age = app.config["ACCOUNT_ACTIVATION_MAX_AGE"]
    app.config["ACCOUNT_ACTIVATION_MAX_AGE"] = -1
    assert api.post("/api/auth/activate", {"token": token}).status_code == 400
    app.config["ACCOUNT_ACTIVATION_MAX_AGE"] = original_age
    response = api.post("/api/auth/activation/resend", {"email": " ANDRES@Example.COM "})
    assert response.status_code == 202
    assert len(outbox(app)) == 2
    token = link_token(outbox(app)[-1], "activar")
    assert api.post("/api/auth/activate", {"token": token}).status_code == 200
    assert api.post("/api/auth/activation/resend", {"email": "andres@example.com"}).status_code == 202
    assert len(outbox(app)) == 2


def test_smtp_failure_preserves_pending_account(api, app, monkeypatch):
    app.config.update(TEST_REAL_SMTP=True, SMTP_HOST="")
    assert api.post("/api/auth/register", register_payload()).status_code == 503
    assert api.login("andres@example.com", GOOD_PASSWORD).status_code == 401
    assert api.post("/api/auth/register", register_payload()).status_code == 409
    assert api.post("/api/auth/activation/resend", {"email": "andres@example.com"}).status_code == 503
    monkeypatch.setitem(app.config, "TEST_REAL_SMTP", False)
    assert api.post("/api/auth/activation/resend", {"email": "andres@example.com"}).status_code == 202
    assert len(outbox(app)) == 1


def test_database_enforces_case_insensitive_email(app):
    from pytest import raises
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        user = User(email=" CLIENTE@FERREPRO.TEST ", full_name="Duplicado")
        user.set_password(GOOD_PASSWORD)
        db.session.add(user)
        with raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_register_validates_password_and_consents(api):
    weak = api.post("/api/auth/register", register_payload(password="corta1", accept_privacy=False))
    assert weak.status_code == 400
    fields = weak.get_json()["fields"]
    assert "password" in fields and "accept_privacy" in fields
    no_digits = api.post("/api/auth/register", register_payload(password="soloLetrasLargas"))
    assert "password" in no_digits.get_json()["fields"]
    invalid_email = api.post("/api/auth/register", register_payload(email="andres..cliente@example.com"))
    assert "email" in invalid_email.get_json()["fields"]
    with_email = api.post("/api/auth/register", register_payload(password="andres2026seguro"))
    assert "password" in with_email.get_json()["fields"]


def test_register_cannot_create_admins(api, app):
    api.post("/api/auth/register", register_payload(role="admin", is_active=True))
    with app.app_context():
        user = User.query.filter_by(email="andres@example.com").one()
        assert user.role == "customer" and not user.is_active


def test_register_is_rate_limited(api):
    codes = [api.post("/api/auth/register", register_payload(email=f"u{i}@example.com")).status_code for i in range(6)]
    assert codes[:5] == [202] * 5 and codes[5] == 429


# ---------------------------------------------------------------- recuperacion

def test_forgot_password_same_answer_for_unknown_email(api, app):
    unknown = api.post("/api/auth/password/forgot", {"email": "nadie@example.com"})
    known = api.post("/api/auth/password/forgot", {"email": "cliente@ferrepro.test"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.get_json() == known.get_json()
    assert [m["to"] for m in outbox(app)] == ["cliente@ferrepro.test"]


def test_reset_password_changes_hash_logs_in_and_link_is_single_use(api, app):
    api.post("/api/auth/password/forgot", {"email": "cliente@ferrepro.test"})
    token = link_token(outbox(app)[-1], "restablecer")
    weak = api.post("/api/auth/password/reset", {"token": token, "password": "123"})
    assert weak.status_code == 400 and "password" in weak.get_json()["fields"]
    ok = api.post("/api/auth/password/reset", {"token": token, "password": "NuevaClave2026xyz"})
    assert ok.status_code == 200 and ok.get_json()["user"]["email"] == "cliente@ferrepro.test"
    again = api.post("/api/auth/password/reset", {"token": token, "password": "OtraClave2026xyz"})
    assert again.status_code == 400 and again.get_json()["error"] == "invalid_link"

    fresh = ApiClient(app.test_client())
    assert fresh.login("cliente@ferrepro.test", "NuevaClave2026xyz").status_code == 200


def test_reset_rejects_tampered_or_foreign_tokens(api, app):
    api.post("/api/auth/password/forgot", {"email": "cliente@ferrepro.test"})
    token = link_token(outbox(app)[-1], "restablecer")
    payload, signature = token.rsplit(".", 1)
    tampered = payload + "." + ("B" if signature[0] == "A" else "A") + signature[1:]
    assert api.post("/api/auth/password/reset", {"token": tampered, "password": "NuevaClave2026xyz"}).status_code == 400
    # Un enlace de activacion no sirve para restablecer (sal distinta)
    api.post("/api/auth/register", register_payload())
    activation = link_token(outbox(app)[-1], "activar")
    assert api.post("/api/auth/password/reset", {"token": activation, "password": "NuevaClave2026xyz"}).status_code == 400


def test_password_change_ends_other_sessions(app):
    first = ApiClient(app.test_client())
    assert first.login("cliente@ferrepro.test", "ClienteSeguro2026").status_code == 200
    second = ApiClient(app.test_client())
    second.post("/api/auth/password/forgot", {"email": "cliente@ferrepro.test"})
    token = link_token(outbox(app)[-1], "restablecer")
    second.post("/api/auth/password/reset", {"token": token, "password": "NuevaClave2026xyz"})
    assert first.get("/api/auth/me").get_json()["user"] is None


def test_disabled_account_gets_no_links(api, app):
    with app.app_context():
        user = User.query.filter_by(email="cliente@ferrepro.test").one()
        user.is_active = False
        user.last_login_at = user.created_at  # ya habia entrado: la desactivo un administrador
        db.session.commit()
    api.post("/api/auth/password/forgot", {"email": "cliente@ferrepro.test"})
    assert outbox(app) == []


# ---------------------------------------------------------------- sesion y roles

def test_login_reports_role_and_rotates_csrf(api):
    before = api.token()
    response = api.login("admin@ferrepro.test", ADMIN_PASSWORD)
    assert response.status_code == 200
    assert response.get_json()["user"]["role"] == "admin"
    assert response.get_json()["csrf"] != before
    cookie_name = api.client.application.config["SESSION_COOKIE_NAME"]
    old_cookie = api.client.get_cookie(cookie_name)
    logout = api.post("/api/auth/logout")
    assert logout.status_code == 200 and logout.get_json()["csrf"] != response.get_json()["csrf"]
    assert api.get("/api/auth/me").get_json()["user"] is None
    with api.client.application.test_client() as old_session:
        old_session.set_cookie(cookie_name, old_cookie.value)
        assert old_session.get("/api/auth/me").get_json()["user"] is None


def test_unknown_and_wrong_password_get_same_message(api):
    unknown = api.login("nadie@example.com", "Cualquiera2026x")
    wrong = api.login("cliente@ferrepro.test", "Cualquiera2026x")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.get_json() == wrong.get_json()


def test_session_cookie_flags(api):
    response = api.login("cliente@ferrepro.test", "ClienteSeguro2026")
    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
