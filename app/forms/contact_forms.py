from app.forms.privacy import PrivacyForm
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length


class ContactForm(PrivacyForm):
    """Formulario de contacto para clientes y visitantes."""
    full_name = StringField('Nombre completo', validators=[
        DataRequired(message="Por favor introduce tu nombre completo."),
        Length(min=3, max=150, message="El nombre debe tener entre 3 y 150 caracteres.")
    ])
    email = StringField('Correo electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio."),
        Email(check_deliverability=False, message="Introduce una dirección de correo válida."), Length(max=255)
    ])
    phone = StringField('Teléfono de contacto', validators=[
        Length(max=30, message="El teléfono no puede exceder 30 caracteres.")
    ])
    subject = SelectField('Asunto de tu consulta', choices=[
        ('consulta_producto', 'Consulta sobre disponibilidad o precio de producto'),
        ('cotizacion_obra', 'Cotización mayorista para obra / construcción'),
        ('estado_pedido', 'Seguimiento o estado de un pedido'),
        ('garantia_soporte', 'Garantías, devoluciones o soporte técnico'),
        ('otro', 'Otro asunto general')
    ], validators=[
        DataRequired(message="Selecciona un asunto.")
    ])
    message = TextAreaField('Mensaje o requerimiento', validators=[
        DataRequired(message="El mensaje no puede estar vacío."),
        Length(min=10, max=2500, message="El mensaje debe contener entre 10 y 2500 caracteres.")
    ])
    submit = SubmitField('Enviar Mensaje')
