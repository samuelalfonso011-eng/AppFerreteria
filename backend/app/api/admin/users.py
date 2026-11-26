"""Administración de cuentas. Las bajas son reversibles y revocan sesiones."""
from flask import abort, jsonify, request

from sqlalchemy.exc import IntegrityError

from app.api.admin import admin_bp
from app.extensions import db
from app.models import User
from app.models.user import AuthSession
from app.services.auth_service import password_problem
from app.utils.http import json_error
from app.utils.security import current_user
from app.utils.timeutils import iso
from app.utils.validation import Validator


def _view(user):
    return dict(user.to_session(), id=user.id, is_active=user.is_active,
                email_verification_pending=user.email_verification_pending, created_at=iso(user.created_at))


@admin_bp.get("/users")
def list_users():
    page = max(1, min(request.args.get("page", 1, type=int), 10_000))
    result = User.query.order_by(User.id).paginate(page=page, per_page=25, error_out=False)
    return jsonify(users=[_view(user) for user in result.items], page=page,
                   pages=max(1, result.pages), total=result.total)


@admin_bp.post("/users")
def create_user():
    v = Validator(request.get_json(silent=True))
    name = v.text("name", 150, min_len=3)
    email = v.email("email")
    role = v.choice("role", User.ROLES)
    active = v.boolean("is_active", default=True)
    password = v.data.get("password")
    problem = password_problem(password, email)
    if problem:
        v.error("password", problem)
    v.raise_if_errors()

    user = User(full_name=name, email=email, role=role, is_active=active)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if User.by_email(email) is None:
            raise
        return json_error(409, "email_taken", "Ya existe una cuenta con ese correo.")
    return jsonify(user=_view(user)), 201


@admin_bp.patch("/users/<int:user_id>")
def update_user(user_id):
    actor_id = current_user().id
    # Serializa los cambios de privilegios entre administradores activos.
    admins = (User.query.filter_by(role=User.ROLE_ADMIN, is_active=True)
              .order_by(User.id).populate_existing().with_for_update().all())
    if actor_id not in {admin.id for admin in admins if not admin.email_verification_pending}:
        abort(403)
    user = db.session.get(User, user_id, with_for_update=True, populate_existing=True)
    if user is None:
        abort(404)
    v = Validator(request.get_json(silent=True))
    if "role" not in v.data and "is_active" not in v.data:
        v.error("user", "Envía el rol o el estado de la cuenta.")
    role = v.choice("role", User.ROLES) if "role" in v.data else user.role
    active = v.boolean("is_active", default=user.is_active)
    v.raise_if_errors()
    if user.id == actor_id and (role != User.ROLE_ADMIN or not active):
        return json_error(409, "own_admin_account", "Tu cuenta debe conservar el acceso de administrador.")

    if role != user.role or active != user.is_active or "is_active" in v.data:
        AuthSession.query.filter_by(user_id=user.id).delete()
    user.role = role
    user.is_active = active
    if "is_active" in v.data:
        user.email_verification_pending = False
    db.session.commit()
    return jsonify(user=_view(user))
