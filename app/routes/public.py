from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models.category import Category
from app.models.product import Product
from app.models.setting import StoreSetting
from app.models.contact import ContactMessage
from app.forms.contact_forms import ContactForm
from app.utils.anti_spam import (
    is_honeypot_triggered,
    is_submitted_too_fast,
    check_rate_limit,
    contains_excessive_links,
    generate_form_token,
    render_rate_limit_error
)

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def home():
    """Página principal de la ferretería con categorías, destacados y ofertas."""
    settings = StoreSetting.get_settings()
    
    # Categorías activas
    categories = Category.query.filter_by(is_active=True).all()
    
    # Productos destacados (activos y con inventario) con joinedload
    featured_products = Product.query.options(joinedload(Product.category)).filter_by(is_active=True).filter(Product.stock > 0).limit(8).all()
    
    # Novedades (productos añadidos recientemente) con joinedload
    recent_products = Product.query.options(joinedload(Product.category)).filter_by(is_active=True).order_by(Product.created_at.desc()).limit(4).all()

    return render_template(
        'home.html',
        settings=settings,
        categories=categories,
        featured_products=featured_products,
        recent_products=recent_products
    )


@public_bp.route('/nosotros')
def about():
    """Página institucional de la ferretería."""
    settings = StoreSetting.get_settings()
    return render_template('about.html', settings=settings)


@public_bp.route('/contacto', methods=['GET', 'POST'])
def contact():
    """Página de contacto, formulario de atención y ubicación física con blindaje anti-spam."""
    settings = StoreSetting.get_settings()
    form = ContactForm()

    if request.method == 'POST':
        # 1. Rate limiting por IP
        if not check_rate_limit('contact', limit=5, window_seconds=60):
            return render_rate_limit_error("Has alcanzado el límite de mensajes permitidos por minuto. Por favor espera unos momentos antes de reintentar.")

        # 2. Trampa Honeypot para bots
        if is_honeypot_triggered(request.form, 'website_url'):
            flash("¡Gracias por contactarnos! Tu mensaje ha sido recibido exitosamente. Nos comunicaremos contigo en breve.", "success")
            return redirect(url_for('public.contact'))

        # 3. Verificación de velocidad de llenado (Time-based token)
        form_token = request.form.get('form_token', '')
        if is_submitted_too_fast(form_token, min_seconds=2.0):
            flash("El formulario fue enviado con demasiada rapidez. Por favor tómate un momento e intenta de nuevo.", "warning")
            return redirect(url_for('public.contact'))

        # 4. Detección de inyecciones de enlaces excesivos
        if form.message.data and contains_excessive_links(form.message.data, max_links=2):
            flash("Tu mensaje contiene demasiados enlaces sospechosos. Por favor remueve URLs innecesarias.", "danger")
            return render_template('contact.html', settings=settings, form=form, form_token=generate_form_token())

        if form.validate_on_submit():
            contact_msg = ContactMessage(
                full_name=form.full_name.data.strip(),
                email=form.email.data.strip().lower(),
                phone=form.phone.data.strip() if form.phone.data else None,
                subject=form.subject.data,
                message=form.message.data.strip()
            )
            db.session.add(contact_msg)
            db.session.commit()
            flash("¡Gracias por contactarnos! Tu mensaje ha sido recibido exitosamente. Nos comunicaremos contigo en breve.", "success")
            return redirect(url_for('public.contact'))

    return render_template('contact.html', settings=settings, form=form, form_token=generate_form_token())


@public_bp.route('/entregas')
def delivery_info():
    """Información sobre políticas de entregas a domicilio y tarifas."""
    settings = StoreSetting.get_settings()
    return render_template('delivery_info.html', settings=settings)


# ==============================================================================
# PÁGINAS LEGALES Y PRIVACIDAD
# ==============================================================================

@public_bp.route('/politica-de-privacidad')
def privacy_policy():
    """Política de tratamiento de datos personales y privacidad."""
    settings = StoreSetting.get_settings()
    return render_template('legal/privacy.html', settings=settings)


@public_bp.route('/terminos-y-condiciones')
def terms_conditions():
    """Términos y condiciones de uso de la tienda y pedidos."""
    settings = StoreSetting.get_settings()
    return render_template('legal/terms.html', settings=settings)


@public_bp.route('/politica-de-cookies')
def cookies_policy():
    """Política de uso de cookies y preferencias técnicas."""
    settings = StoreSetting.get_settings()
    return render_template('legal/cookies.html', settings=settings)


@public_bp.route('/politica-de-reembolsos')
def refunds_policy():
    """Política de reembolsos, devoluciones y garantías según Ley 1480 y Decreto 587."""
    settings = StoreSetting.get_settings()
    return render_template('legal/refunds.html', settings=settings)


@public_bp.route('/set-language/<lang>')
def set_language(lang):
    """Permite alternar entre Español (es) e Inglés (en) guardándolo en la sesión."""
    if lang in ['es', 'en']:
        session['lang'] = lang
    referrer = request.referrer
    if referrer and referrer.startswith(request.host_url):
        return redirect(referrer)
    return redirect(url_for('public.home'))


