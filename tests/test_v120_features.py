"""
Pruebas exhaustivas para la versión 1.2.0 de Ferretería El Constructor:
- Validación exclusiva de los 10 municipios del Valle de Aburrá.
- Asignación interna por defecto del departamento Antioquia.
- Páginas legales colombianas (Ley 1581 Habeas Data, Ley 1480 Estatuto del Consumidor, SIC, Cookies).
- Internacionalización completa ES / EN.
- Rediseño y validación de formulario de contacto.
"""

import pytest
from app.constants import VALLE_DE_ABURRA_MUNICIPALITIES, DEFAULT_DEPARTMENT
from app.models.user import Address
from app.models.contact import ContactMessage
from app.extensions import db


def test_valle_de_aburra_municipalities_list():
    """Verifica que la lista oficial contenga exactamente los 10 municipios del Valle de Aburrá."""
    assert len(VALLE_DE_ABURRA_MUNICIPALITIES) == 10
    expected = [
        "Medellín", "Bello", "Itagüí", "Envigado", "Sabaneta",
        "Copacabana", "La Estrella", "Girardota", "Caldas", "Barbosa"
    ]
    for m in expected:
        assert m in VALLE_DE_ABURRA_MUNICIPALITIES


def test_address_book_valle_de_aburra_success(client, app):
    """Verifica que un cliente pueda guardar una dirección con un municipio válido del Valle de Aburrá."""
    client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}, follow_redirects=True)
    
    res = client.post('/perfil/direcciones', data={
        'recipient_name': 'Carlos Arango',
        'phone': '300 123 4567',
        'city': 'Envigado',
        'neighborhood': 'Zúñiga',
        'street_address': 'Calle 25 Sur # 42-10',
        'complement': 'Apto 402',
        'delivery_instructions': 'Tocar timbre 402',
        'accept_privacy': 'y',
        'is_default': 'y'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Direcci\xc3\xb3n guardada exitosamente" in res.data or b"guardada" in res.data

    with app.app_context():
        addr = Address.query.filter_by(recipient_name='Carlos Arango').first()
        assert addr is not None
        assert addr.city == 'Envigado'
        assert addr.department == 'Antioquia'  # Asignado automáticamente sin pedir al usuario


def test_address_book_rejects_non_valle_de_aburra(client, app):
    """Verifica que municipios fuera del Valle de Aburrá sean rechazados."""
    client.post('/login', data={'email': 'cliente@correo.com', 'password': 'ClientePass123*'}, follow_redirects=True)
    
    res = client.post('/perfil/direcciones', data={
        'recipient_name': 'Persona Bogota',
        'phone': '300 999 8888',
        'city': 'Bogotá',
        'neighborhood': 'Chapinero',
        'street_address': 'Carrera 7 # 60-20'
    }, follow_redirects=True)

    # Debe rebotar porque no es una opción válida en SelectField / route check
    with app.app_context():
        addr = Address.query.filter_by(recipient_name='Persona Bogota').first()
        assert addr is None


def test_colombian_legal_pages_compliance(client):
    """Verifica que las páginas legales cumplan con los marcos jurídicos colombianos (Ley 1581, Ley 1480, SIC)."""
    # 1. Política de Privacidad (Ley 1581 de 2012)
    res_privacy = client.get('/politica-de-privacidad')
    assert res_privacy.status_code == 200
    assert b"1581" in res_privacy.data
    assert b"Habeas Data" in res_privacy.data
    assert b"Superintendencia de Industria y Comercio" in res_privacy.data
    assert b"diez (10) d\xc3\xadas h\xc3\xa1biles" in res_privacy.data or b"diez" in res_privacy.data

    # 2. Términos y Condiciones (Ley 1480 de 2011)
    res_terms = client.get('/terminos-y-condiciones')
    assert res_terms.status_code == 200
    assert b"1480" in res_terms.data
    assert b"Valle de Aburr\xc3\xa1" in res_terms.data
    assert b"Retracto" in res_terms.data
    assert b"cables" in res_terms.data or b"Cables" in res_terms.data
    assert b"Sandbox" in res_terms.data or b"simulado" in res_terms.data

    # 3. Política de Cookies
    res_cookies = client.get('/politica-de-cookies')
    assert res_cookies.status_code == 200
    assert b"session" in res_cookies.data
    assert b"csrf_token" in res_cookies.data
    assert b"theme" in res_cookies.data


def test_internationalization_toggle_and_rendering(client):
    """Verifica que cambiar de idioma entre ES y EN traduzca elementos clave del Home y Navegación."""
    # Cambiar a EN
    res_en = client.get('/set-language/en', follow_redirects=True)
    assert res_en.status_code == 200
    res_home_en = client.get('/')
    assert b"Catalog" in res_home_en.data or b"Cart" in res_home_en.data
    assert b"Explore Catalog" in res_home_en.data or b"Materials and tools" in res_home_en.data

    # Cambiar a ES
    res_es = client.get('/set-language/es', follow_redirects=True)
    assert res_es.status_code == 200
    res_home_es = client.get('/')
    assert b"Cat\xc3\xa1logo" in res_home_es.data
    assert b"Carrito" in res_home_es.data


def test_contact_form_layout_and_persistence(client, app):
    """Verifica que el formulario de contacto funcione y persista el mensaje."""
    res_get = client.get('/contacto')
    assert res_get.status_code == 200
    assert b"Valle de Aburr\xc3\xa1" in res_get.data
    assert b"Env\xc3\xadanos un Mensaje" in res_get.data

    res_post = client.post('/contacto', data={
        'full_name': 'Ingeniero Constructor',
        'email': 'ingeniero@constructora.com',
        'phone': '310 555 1234',
        'subject': 'cotizacion_obra',
        'message': 'Requerimos cotización formal para 50 bultos de cemento y herramientas eléctricas.',
        'accept_privacy': 'y'
    }, follow_redirects=True)

    assert res_post.status_code == 200
    assert b"recibido exitosamente" in res_post.data or b"Gracias por contactarnos" in res_post.data

    with app.app_context():
        msg = ContactMessage.query.filter_by(email='ingeniero@constructora.com').first()
        assert msg is not None
        assert msg.subject == 'cotizacion_obra'
