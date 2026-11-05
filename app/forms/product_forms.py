from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, InputRequired, Optional, NumberRange, Length, ValidationError
from app.models.product import Product
from app.models.category import Category


class ProductForm(FlaskForm):
    name = StringField('Nombre del producto', validators=[
        DataRequired(message="El nombre es obligatorio."),
        Length(min=2, max=200)
    ])
    category_id = SelectField('Categoría', coerce=int, validators=[
        DataRequired(message="Selecciona una categoría.")
    ])
    sku = StringField('Código SKU', validators=[
        DataRequired(message="El código SKU es obligatorio."),
        Length(min=2, max=50)
    ])
    description = TextAreaField('Descripción comercial', validators=[
        DataRequired(message="La descripción es obligatoria.")
    ])
    technical_specs = TextAreaField('Características técnicas')
    price = DecimalField('Precio unitario ($)', places=2, validators=[
        InputRequired(message="El precio es obligatorio."),
        NumberRange(min=0, message="El precio no puede ser negativo.")
    ])
    stock = IntegerField('Cantidad en existencias', validators=[
        InputRequired(message="El stock inicial es obligatorio."),
        NumberRange(min=0, message="El stock no puede ser negativo.")
    ])
    min_stock_alert = IntegerField('Alerta de stock mínimo', default=5, validators=[
        InputRequired(message="Define el umbral mínimo de inventario."),
        NumberRange(min=0, message="El umbral mínimo no puede ser negativo.")
    ])
    image = FileField('Imagen del producto', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Solo se permiten imágenes (.jpg, .jpeg, .png, .webp).')
    ])
    is_active = BooleanField('Producto activo para la venta', default=True)
    submit = SubmitField('Guardar producto')

    def __init__(self, original_sku=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_sku = original_sku
        if original_sku is not None:
            # En edición el stock no se modifica aquí (se usa el ajuste de inventario con kárdex)
            self.stock.validators = [Optional()]
        self.category_id.choices = [
            (c.id, c.name) for c in Category.query.filter_by(is_active=True).order_by(Category.name).all()
        ]

    def validate_sku(self, field):
        sku_val = field.data.strip().upper()
        if sku_val != self.original_sku:
            if Product.query.filter_by(sku=sku_val).first():
                raise ValidationError("Este código SKU ya está asignado a otro producto.")


class CategoryForm(FlaskForm):
    name = StringField('Nombre de la categoría', validators=[
        DataRequired(message="El nombre de la categoría es obligatorio."),
        Length(min=2, max=100)
    ])
    description = TextAreaField('Descripción')
    is_active = BooleanField('Categoría activa', default=True)
    submit = SubmitField('Guardar categoría')

    def __init__(self, original_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, field):
        normalized = Category.normalize_name(field.data)
        if self.original_name and Category.normalize_name(self.original_name).lower() == normalized.lower():
            return
        if Category.query.filter(Category.name.ilike(normalized)).first():
            raise ValidationError("Ya existe una categoría con este nombre.")
