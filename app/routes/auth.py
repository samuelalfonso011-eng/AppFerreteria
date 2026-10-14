from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from app.extensions import db
from app.models.user import User, Role, Address
from app.forms.auth_forms import (
    LoginForm, RegisterForm, ProfileForm, AddressForm,
    ForgotPasswordForm, ResetPasswordForm
)
from app.services.cart_service import CartService

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/registro', methods=['GET', 'POST'])
def register():
    """Registro público abierto exclusivo para rol de clientes."""
    if current_user.is_authenticated:
        return redirect(url_for('public.home'))

    form = RegisterForm()
    if form.validate_on_submit():
        # Obtener o asegurar el rol de 'customer'
        customer_role = Role.query.filter_by(name='customer').first()
        if not customer_role:
            customer_role = Role(name='customer', description='Cliente de la tienda')
            db.session.add(customer_role)
            db.session.flush()

        # Las cuentas nuevas reciben estrictamente el rol de cliente
        user = User(
            email=form.email.data.strip().lower(),
            full_name=form.full_name.data.strip(),
            phone=form.phone.data.strip() if form.phone.data else None,
            role_id=customer_role.id,
            is_active=True
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        # Iniciar sesión automáticamente
        login_user(user)

        # Sincronizar carrito de visitante previo si existe
        CartService.sync_guest_cart_to_user(user)

        flash(f"¡Bienvenido, {user.full_name}! Tu cuenta ha sido creada exitosamente.", "success")
        return redirect(url_for('public.home'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión con hash seguro y sincronización de carrito."""
    if current_user.is_authenticated:
        return redirect(url_for('public.home'))

    form = LoginForm()
    if form.validate_on_submit():
        email_clean = form.email.data.strip().lower()
        user = User.query.filter_by(email=email_clean).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash("Tu cuenta ha sido desactivada. Por favor contacta al administrador.", "danger")
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember.data)

            # Sincronizar carrito de visitante con la base de datos
            CartService.sync_guest_cart_to_user(user)

            flash(f"¡Hola de nuevo, {user.full_name}!", "success")

            # Redirección segura evitando ataques de Open Redirect
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if user.is_admin:
                return redirect(url_for('admin_dashboard.index'))
            return redirect(url_for('public.home'))

        flash("Correo electrónico o contraseña incorrectos.", "danger")

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Cierre de sesión seguro en el servidor."""
    logout_user()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for('public.home'))


@auth_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def profile():
    """Perfil del cliente: consultar y editar datos personales."""
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        current_user.phone = form.phone.data.strip() if form.phone.data else None
        db.session.commit()
        flash("Tus datos personales han sido actualizados.", "success")
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', form=form)


@auth_bp.route('/perfil/direcciones', methods=['GET', 'POST'])
@login_required
def addresses():
    """Gestión de la libreta de direcciones de entrega del cliente."""
    form = AddressForm()
    if form.validate_on_submit():
        # Si se marca como default, desmarcar las anteriores
        if form.is_default.data:
            Address.query.filter_by(user_id=current_user.id).update({'is_default': False})

        new_addr = Address(
            user_id=current_user.id,
            recipient_name=form.recipient_name.data.strip(),
            phone=form.phone.data.strip(),
            department=form.department.data.strip(),
            city=form.city.data.strip(),
            neighborhood=form.neighborhood.data.strip(),
            street_address=form.street_address.data.strip(),
            complement=form.complement.data.strip() if form.complement.data else None,
            delivery_instructions=form.delivery_instructions.data.strip() if form.delivery_instructions.data else None,
            is_default=form.is_default.data
        )
        db.session.add(new_addr)
        db.session.commit()
        flash("Dirección guardada exitosamente.", "success")
        return redirect(url_for('auth.addresses'))

    user_addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
    return render_template('auth/addresses.html', form=form, addresses=user_addresses)


@auth_bp.route('/perfil/direcciones/<int:address_id>/eliminar', methods=['POST'])
@login_required
def delete_address(address_id):
    """Elimina una dirección propia del cliente."""
    addr = Address.query.filter_by(id=address_id, user_id=current_user.id).first_or_404()
    db.session.delete(addr)
    db.session.commit()
    flash("Dirección eliminada.", "info")
    return redirect(url_for('auth.addresses'))


@auth_bp.route('/perfil/direcciones/<int:address_id>/predeterminada', methods=['POST'])
@login_required
def set_default_address(address_id):
    """Establece una dirección como predeterminada."""
    addr = Address.query.filter_by(id=address_id, user_id=current_user.id).first_or_404()
    Address.query.filter_by(user_id=current_user.id).update({'is_default': False})
    addr.is_default = True
    db.session.commit()
    flash("Dirección establecida como principal.", "success")
    return redirect(url_for('auth.addresses'))


# ==============================================================================
# RECUPERACIÓN DE CONTRASEÑA (TOKENS CRIPTOGRÁFICOS ITSDANGEROUS)
# ==============================================================================

def get_reset_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def generate_reset_token(user_id: int) -> str:
    """Genera un token firmado con sal específica para restablecimiento de contraseña."""
    s = get_reset_serializer()
    return s.dumps(user_id, salt='password-reset-salt')


def verify_reset_token(token: str, max_age: int = 1800) -> int:
    """Verifica la validez y expiración del token (30 minutos = 1800s). Retorna user_id o None."""
    s = get_reset_serializer()
    try:
        user_id = s.loads(token, salt='password-reset-salt', max_age=max_age)
        return user_id
    except Exception:
        return None


@auth_bp.route('/recuperar-password', methods=['GET', 'POST'])
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Formulario para solicitar restablecimiento de contraseña."""
    if current_user.is_authenticated:
        return redirect(url_for('public.home'))

    form = ForgotPasswordForm()
    dev_reset_url = None

    if form.validate_on_submit():
        email_clean = form.email.data.strip().lower()
        user = User.query.filter_by(email=email_clean).first()

        if user:
            token = generate_reset_token(user.id)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            dev_reset_url = reset_url
            current_app.logger.info(f"[RECUPERACIÓN CONTRASEÑA] Token generado para {email_clean}: {reset_url}")
            print(f"\n=======================================================")
            print(f" [ENLACE DE RECUPERACIÓN DE CONTRASEÑA]")
            print(f" Para: {email_clean}")
            print(f" Enlace: {reset_url}")
            print(f" Válido por: 30 minutos")
            print(f"=======================================================\n")
            flash("Hemos enviado las instrucciones para restablecer tu contraseña. Revisa tu bandeja de entrada.", "info")
            return render_template('auth/forgot_password.html', form=form, dev_reset_url=dev_reset_url)
        else:
            # Mensaje preventivo idéntico para evitar enumeración de correos
            flash("Si el correo electrónico está registrado, recibirás un enlace de recuperación.", "info")
            return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form, dev_reset_url=dev_reset_url)


@auth_bp.route('/restablecer-password/<token>', methods=['GET', 'POST'])
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Establece una nueva contraseña utilizando un token válido y no expirado."""
    if current_user.is_authenticated:
        return redirect(url_for('public.home'))

    user_id = verify_reset_token(token, max_age=1800)
    if not user_id:
        flash("El enlace de recuperación es inválido o ha expirado (más de 30 minutos). Por favor solicita uno nuevo.", "danger")
        return redirect(url_for('auth.forgot_password'))

    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        flash("Usuario no encontrado o cuenta desactivada.", "danger")
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("¡Tu contraseña ha sido restablecida con éxito! Ya puedes iniciar sesión con tu nueva clave.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form, token=token)

