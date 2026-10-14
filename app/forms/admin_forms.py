from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, TextAreaField, DecimalField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Length, Optional
from app.models.order import OrderStatus


class StockAdjustmentForm(FlaskForm):
    target_stock = IntegerField('Nuevo stock total en existencias', validators=[
        DataRequired(message="El nuevo stock es obligatorio."),
        NumberRange(min=0, message="El stock no puede ser negativo.")
    ])
    reason = StringField('Motivo u observación del ajuste', validators=[
        DataRequired(message="Debes justificar el motivo del ajuste."),
        Length(min=3, max=255)
    ])
    submit = SubmitField('Registrar ajuste en Kárdex')


class OrderStatusForm(FlaskForm):
    new_status = SelectField('Nuevo estado del pedido', choices=[
        (OrderStatus.CONFIRMED, OrderStatus.LABELS[OrderStatus.CONFIRMED]),
        (OrderStatus.PREPARING, OrderStatus.LABELS[OrderStatus.PREPARING]),
        (OrderStatus.SHIPPED, OrderStatus.LABELS[OrderStatus.SHIPPED]),
        (OrderStatus.DELIVERED, OrderStatus.LABELS[OrderStatus.DELIVERED]),
        (OrderStatus.CANCELLED, OrderStatus.LABELS[OrderStatus.CANCELLED]),
    ], validators=[DataRequired()])
    comment = TextAreaField('Observación o comentario del cambio', validators=[
        Optional(),
        Length(max=500)
    ])
    submit = SubmitField('Actualizar estado')


class StoreSettingForm(FlaskForm):
    store_name = StringField('Nombre comercial', validators=[
        DataRequired(message="El nombre es obligatorio."),
        Length(max=150)
    ])
    phone = StringField('Teléfono de atención', validators=[
        DataRequired(message="El teléfono es obligatorio."),
        Length(max=50)
    ])
    email = StringField('Correo de contacto', validators=[
        DataRequired(message="El correo es obligatorio."),
        Length(max=100)
    ])
    address = StringField('Dirección física de la ferretería', validators=[
        DataRequired(message="La dirección es obligatoria."),
        Length(max=255)
    ])
    business_hours = StringField('Horario de atención', validators=[
        DataRequired(message="El horario es obligatorio."),
        Length(max=255)
    ])
    default_shipping_cost = DecimalField('Costo de envío estándar ($)', places=2, validators=[
        DataRequired(message="El costo de envío es obligatorio."),
        NumberRange(min=0, message="El costo de envío no puede ser negativo.")
    ])
    free_shipping_threshold = DecimalField('Monto para envío gratis ($)', places=2, validators=[
        Optional(),
        NumberRange(min=0, message="El monto de envío gratis no puede ser negativo.")
    ])
    submit = SubmitField('Guardar configuración')
