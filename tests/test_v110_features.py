"""
Pruebas automatizadas de las características introducidas en la versión 1.1.0:
- Páginas legales y políticas (Privacidad, Términos, Cookies)
- Formulario de contacto funcional y persistencia de mensajes
- Flujo seguro de recuperación y restablecimiento de contraseña
- Alternancia de idioma (ES / EN)
- Carga de recursos vectoriales e identidad visual
- Estructura y clases del layout administrativo responsivo
"""

import pytest
from app.extensions import db
from app.models.user import User
from app.models.contact import ContactMessage
from app.routes.auth import generate_reset_token


def test_legal_pages_respond_200(client):
    """Verifica que las rutas legales respondan 200 OK y contengan información requerida."""
    pages = [
        ('/politica-de-privacidad', 'Tratamiento de Datos Personales'),
        ('/terminos-y-condiciones', 'Términos y Condiciones'),
        ('/politica-de-cookies', 'Política de Cookies'),
    ]
    for url, keyword in pages:
        res = client.get(url)
        assert res.status_code == 200
        assert keyword.encode('utf-8') in res.data or keyword in res.data.decode('utf-8', errors='ignore')


def test_contact_form_get_and_post(client, app):
    """Verifica la visualización y el envío exitoso del formulario de contacto."""
    # GET
    res_get = client.get('/contacto')
    assert res_get.status_code == 200
    assert 'Enviar Mensaje'.encode('utf-8') in res_get.data

    # POST válido con key de choice en el formulario
    payload = {
        'full_name': 'Carlos Mendoza',
        'email': 'carlos@ejemplo.com',
        'phone': '310 999 8888',
        'subject': 'consulta_producto',
        'message': 'Buenas tardes, quisiera consultar la disponibilidad de 50 martillos para obra.',
        'accept_privacy': 'y'
    }
    res_post = client.post('/contacto', data=payload, follow_redirects=True)
    assert res_post.status_code == 200
    assert 'recibido exitosamente'.encode('utf-8') in res_post.data

    # Verificar que el mensaje se guardó en la base de datos
    with app.app_context():
        saved_msg = ContactMessage.query.filter_by(email='carlos@ejemplo.com').first()
        assert saved_msg is not None
        assert saved_msg.full_name == 'Carlos Mendoza'
        assert saved_msg.subject == 'consulta_producto'


def test_contact_form_invalid_email_rejected(client, app):
    """Verifica que correos con formato inválido sean rechazados por el validador."""
    payload = {
        'full_name': 'Carlos Mendoza',
        'email': 'correo_invalido_sin_arroba',
        'subject': 'garantia_soporte',
        'message': 'Mensaje de prueba con correo inválido.',
        'accept_privacy': 'y'
    }
    res = client.post('/contacto', data=payload, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        msg = ContactMessage.query.filter_by(full_name='Carlos Mendoza', subject='garantia_soporte').first()
        assert msg is None


def test_password_reset_flow(client, app):
    """Verifica el flujo completo de recuperación y cambio de contraseña con token firmado."""
    # 1. Solicitar recuperación
    res_req = client.post('/recuperar-password', data={'email': 'cliente@correo.com'}, follow_redirects=True)
    assert res_req.status_code == 200
    assert 'instrucciones para restablecer'.encode('utf-8') in res_req.data

    # 2. Generar token firmado en contexto con el ID del usuario
    with app.app_context():
        user = User.query.filter_by(email='cliente@correo.com').first()
        assert user is not None
        token = generate_reset_token(user.id)
        assert token is not None

    # 3. Acceder al formulario de restablecimiento con el token
    res_token_page = client.get(f'/restablecer-password/{token}')
    assert res_token_page.status_code == 200
    assert 'Nueva Contraseña'.encode('utf-8') in res_token_page.data

    # 4. Enviar nueva contraseña
    res_new_pass = client.post(
        f'/restablecer-password/{token}',
        data={
            'password': 'NuevaPassword2026*',
            'confirm_password': 'NuevaPassword2026*'
        },
        follow_redirects=True
    )
    assert res_new_pass.status_code == 200
    assert 'restablecida con éxito'.encode('utf-8') in res_new_pass.data

    # 5. Comprobar que el usuario ahora puede iniciar sesión con la nueva contraseña
    res_login = client.post('/login', data={'email': 'cliente@correo.com', 'password': 'NuevaPassword2026*'}, follow_redirects=True)
    assert res_login.status_code == 200
    assert '¡Hola de nuevo'.encode('utf-8') in res_login.data

    # 6. Comprobar que la contraseña antigua ya no funciona
    client.post('/logout')
    res_old_login = client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}, follow_redirects=True)
    assert 'contraseña incorrectos'.encode('utf-8') in res_old_login.data


def test_password_reset_invalid_token(client):
    """Verifica que un token alterado o inválido sea rechazado adecuadamente."""
    res = client.get('/restablecer-password/token_invalido_totalmente_falso', follow_redirects=True)
    assert res.status_code == 200
    assert 'inválido o ha expirado'.encode('utf-8') in res.data


def test_language_switch(client):
    """Verifica que la alternancia de idioma guarde la preferencia en la sesión."""
    # Cambiar a inglés
    res_en = client.get('/set-language/en', follow_redirects=True)
    assert res_en.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get('lang') == 'en'

    # Cambiar a español
    res_es = client.get('/set-language/es', follow_redirects=True)
    assert res_es.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get('lang') == 'es'


def test_vector_assets_available(client):
    """Verifica que los iconos y recursos vectoriales esenciales en static/img respondan 200."""
    assets = [
        '/static/img/favicon.svg',
        '/static/img/logo.svg',
        '/static/img/hero-banner.svg',
        '/static/img/placeholder-product.svg',
        '/static/img/temp/herramientas.svg',
    ]
    for asset in assets:
        res = client.get(asset)
        assert res.status_code == 200
        assert 'svg' in res.content_type.lower() or b'<svg' in res.data


def test_admin_layout_classes_and_elements(client):
    """Verifica que el panel administrativo incluya el nuevo layout no bloqueante y controles."""
    # Iniciar sesión como administrador
    client.post('/login', data={'email': 'admin@ferreteria.com', 'password': 'AdminPass123*'}, follow_redirects=True)

    res = client.get('/admin/')
    assert res.status_code == 200
    html = res.data.decode('utf-8', errors='ignore')

    assert 'admin-layout' in html
    assert 'admin-sidebar' in html
    assert 'admin-main' in html
    assert 'adminSidebarOverlay' in html
    assert 'adminMenuToggle' in html
