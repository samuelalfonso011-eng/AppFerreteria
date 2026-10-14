from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from app.models.payment import PaymentMethod


class CheckoutForm(FlaskForm):
    # Selección de dirección guardada (0 para nueva dirección)
    saved_address_id = SelectField('Direcciones guardadas', coerce=int, default=0)

    # Campos para dirección de entrega
    recipient_name = StringField('Nombre de quien recibe', validators=[
        DataRequired(message="El nombre de quien recibe es obligatorio."),
        Length(max=150)
    ])
    phone = StringField('Teléfono de contacto', validators=[
        DataRequired(message="El teléfono es obligatorio."),
        Length(max=30)
    ])
    department = StringField('Departamento o Región', validators=[
        DataRequired(message="El departamento es obligatorio."),
        Length(max=100)
    ])
    city = StringField('Ciudad o Municipio', validators=[
        DataRequired(message="La ciudad es obligatoria."),
        Length(max=100)
    ])
    neighborhood = StringField('Barrio', validators=[
        DataRequired(message="El barrio es obligatorio."),
        Length(max=100)
    ])
    street_address = StringField('Dirección exacta', validators=[
        DataRequired(message="La dirección exacta es obligatoria."),
        Length(max=255)
    ])
    complement = StringField('Complemento (Apto, Interior, Manzana)', validators=[
        Optional(),
        Length(max=100)
    ])
    delivery_instructions = TextAreaField('Instrucciones para el domiciliario', validators=[
        Optional()
    ])

    save_to_address_book = BooleanField('Guardar esta dirección en mi libreta de direcciones', default=True)
    notes = TextAreaField('Notas sobre el pedido', validators=[Optional()])
    idempotency_key = HiddenField('Clave de Idempotencia')
    submit = SubmitField('Continuar al pago')


class PaymentSimulationForm(FlaskForm):
    payment_method = SelectField('Método de pago de prueba', choices=[
        (PaymentMethod.SIMULATED_CARD, 'Tarjeta Débito/Crédito (Simulación)'),
        (PaymentMethod.SIMULATED_TRANSFER, 'Transferencia Bancaria (Simulación)'),
        (PaymentMethod.SIMULATED_CASH_ON_DELIVERY, 'Pago contraentrega en efectivo (Simulación)')
    ], validators=[DataRequired(message="Selecciona un método de pago de prueba.")])

    simulated_action = SelectField('Resultado deseado de la simulación', choices=[
        ('approve', 'Aprobar pago (Simular éxito comercial)'),
        ('reject', 'Rechazar pago (Simular fondos insuficientes)'),
        ('pending', 'Dejar pago pendiente (Simular validación de red)')
    ], validators=[DataRequired(message="Selecciona el resultado de la prueba.")])

    submit = SubmitField('Procesar pago de prueba')
