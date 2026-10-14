import pytest
from app.models.user import User
from app.extensions import db


def test_1_visitor_can_browse_catalog(client):
    """Criterio 1: Un visitante puede consultar el catálogo sin iniciar sesión."""
    response = client.get('/productos/')
    assert response.status_code == 200
    assert b"Cat\xc3\xa1logo de Ferreter\xc3\xada" in response.data or b"Catalogo" in response.data


def test_2_customer_can_register(client, app):
    """Criterio 2 y 8: Un cliente puede registrarse y recibe estrictamente el rol de customer."""
    response = client.post('/registro', data={
        'full_name': 'Carlos Gomez',
        'email': 'carlos@ejemplo.com',
        'phone': '3001112233',
        'password': 'Password123*',
        'confirm_password': 'Password123*',
        'role': 'admin',  # Intento malicioso de asignarse admin
        'role_id': 1
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email='carlos@ejemplo.com').first()
        assert user is not None
        assert user.full_name == 'Carlos Gomez'
        # Verificación estricta: Rol asignado SIEMPRE es customer (id=2), nunca admin
        assert user.role.name == 'customer'
        assert not user.is_admin


def test_3_duplicate_emails_rejected(client):
    """Criterio 3: No se permiten cuentas con correos duplicados."""
    response = client.post('/registro', data={
        'full_name': 'Otro Usuario',
        'email': 'cliente@correo.com',  # Ya existente en fixtures
        'password': 'Password123*',
        'confirm_password': 'Password123*'
    })
    assert response.status_code == 200
    assert "Este correo electrónico ya se encuentra registrado".encode('utf-8') in response.data


def test_4_login_and_logout(client):
    """Criterio 4: Un usuario puede iniciar y cerrar sesión."""
    # Login correcto
    response = client.post('/login', data={
        'email': 'cliente@correo.com',
        'password': 'ClientePass123*'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "¡Hola de nuevo, Juan Perez!".encode('utf-8') in response.data

    # Logout
    logout_res = client.get('/logout', follow_redirects=True)
    assert logout_res.status_code == 200
    assert "Has cerrado sesión correctamente".encode('utf-8') in logout_res.data


def test_5_passwords_are_securely_hashed(app):
    """Criterio 5: Las contraseñas no se almacenan en texto plano en la base de datos."""
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        assert user.password_hash != "ClientePass123*"
        assert user.password_hash.startswith("scrypt:") or user.password_hash.startswith("pbkdf2:")
        assert user.check_password("ClientePass123*")
        assert not user.check_password("WrongPassword")


def test_6_customer_cannot_access_admin_panel(client):
    """Criterio 6: Un cliente no puede acceder al panel administrativo (403 Forbidden)."""
    # Iniciar sesión como cliente común
    client.post('/login', data={
        'email': 'cliente@correo.com',
        'password': 'ClientePass123*'
    }, follow_redirects=True)

    # Intentar acceder a ruta administrativa
    response = client.get('/admin/')
    assert response.status_code == 403


def test_admin_can_access_admin_panel(client):
    """Un usuario con rol 'admin' sí puede acceder al panel administrativo."""
    client.post('/login', data={
        'email': 'admin@ferreteria.com',
        'password': 'AdminPass123*'
    }, follow_redirects=True)

    response = client.get('/admin/')
    assert response.status_code == 200
    assert b"Dashboard Comercial" in response.data or b"Dashboard" in response.data
