from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_login import current_user


def admin_required(f):
    """
    Decorador para proteger rutas exclusivas de administración.
    Verifica que el usuario esté autenticado y posea el rol de 'admin'.
    El frontend nunca es la única barrera de seguridad.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Debes iniciar sesión con una cuenta de administrador para acceder.", "warning")
            return redirect(url_for('auth.login'))
        if not current_user.is_active or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
