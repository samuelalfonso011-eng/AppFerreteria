from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.decorators import admin_required
from app.extensions import db
from app.models.category import Category, generate_unique_slug
from app.forms.product_forms import CategoryForm

admin_categories_bp = Blueprint('admin_categories', __name__, url_prefix='/admin/categorias')


@admin_categories_bp.route('/')
@admin_required
def index():
    """Listado de categorías para administración."""
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template('admin/categories/list.html', categories=categories)


@admin_categories_bp.route('/crear', methods=['GET', 'POST'])
@admin_required
def create():
    """Crea una nueva categoría con validación de nombres normalizados."""
    form = CategoryForm()
    if form.validate_on_submit():
        name_clean = Category.normalize_name(form.name.data)
        category = Category(
            name=name_clean,
            slug=generate_unique_slug(name_clean, Category, max_len=120),
            description=form.description.data.strip() if form.description.data else None,
            is_active=form.is_active.data
        )
        db.session.add(category)
        db.session.commit()
        flash(f"Categoría '{category.name}' creada exitosamente.", "success")
        return redirect(url_for('admin_categories.index'))

    return render_template('admin/categories/form.html', form=form, title="Crear Categoría")


@admin_categories_bp.route('/<int:category_id>/editar', methods=['GET', 'POST'])
@admin_required
def edit(category_id):
    """Edita una categoría existente."""
    category = db.get_or_404(Category, category_id)
    form = CategoryForm(original_name=category.name, obj=category)

    if form.validate_on_submit():
        name_clean = Category.normalize_name(form.name.data)
        category.name = name_clean
        category.slug = generate_unique_slug(name_clean, Category, max_len=120, exclude_id=category.id)
        category.description = form.description.data.strip() if form.description.data else None
        category.is_active = form.is_active.data

        db.session.commit()
        flash("Categoría actualizada correctamente.", "success")
        return redirect(url_for('admin_categories.index'))

    return render_template('admin/categories/form.html', form=form, category=category, title="Editar Categoría")


@admin_categories_bp.route('/<int:category_id>/alternar-estado', methods=['POST'])
@admin_required
def toggle_status(category_id):
    """Activa o desactiva una categoría."""
    category = db.get_or_404(Category, category_id)
    category.is_active = not category.is_active
    db.session.commit()
    estado_str = "activada" if category.is_active else "desactivada"
    flash(f"La categoría '{category.name}' ha sido {estado_str}.", "info")
    return redirect(url_for('admin_categories.index'))
