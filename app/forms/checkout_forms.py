from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from app.models.payment import PaymentMethod
from app.constants import MUNICIPALITY_CHOICES, DEFAULT_DEPARTMENT


class CheckoutForm(FlaskForm):
    # Selección de dirección guardada (0 para nueva dirección)
    saved_address_id = SelectField('Direcciones guardadas', coerce=int, default=0)

    # Campos para dirección de entrega (Exclusivo Valle de Aburrá)
    recipient_name = StringField('Nombre de quien recibe', validators=[
        DataRequired(message="El nombre de quien recibe es obligatorio."),
        Length(max=150)
    ])
    phone = StringField('Teléfono de contacto', validators=[
        DataRequired(message="El teléfono celular es obligatorio."),
        Length(max=30)
    ])
    department = HiddenField('Departamento o Región', default=DEFAULT_DEPARTMENT)
    city = SelectField('Municipio (Valle de Aburrá)', choices=MUNICIPALITY_CHOICES, default='Medellín', validators=[
        DataRequired(message="Selecciona un municipio del Valle de Aburrá.")
    ])
    neighborhood = StringField('Barrio o Sector', validators=[
        DataRequired(message="El barrio o sector es obligatorio."),
        Length(max=100)
    ])
    street_address = StringField('Dirección exacta de entrega', validators=[
        DataRequired(message="La dirección exacta de entrega es obligatoria."),
        Length(max=255)
    ])
    complement = StringField('Interior / Apto / Bodega / Obra', validators=[
        Optional(),
        Length(max=100)
    ])
    delivery_instructions = TextAreaField('Indicaciones de entrega para el conductor', validators=[
        Optional()
    ])

    save_to_address_book = BooleanField('Guardar esta dirección en mi libreta de direcciones', default=True)
    notes = TextAreaField('Notas sobre el pedido', validators=[Optional()])

    # Datos para Facturación Electrónica DIAN
    fiscal_doc_type = SelectField('Tipo de Documento Fiscal', choices=[
        ('CC', 'Cédula de Ciudadanía (CC)'),
        ('NIT', 'Número de Identificación Tributaria (NIT)'),
        ('CE', 'Cédula de Extranjería (CE)'),
        ('PP', 'Pasaporte')
    ], default='CC')
    fiscal_doc_number = StringField('Número de Documento / NIT', validators=[Optional(), Length(max=50)])
    fiscal_name = StringField('Razón Social o Nombre Completo para Factura', validators=[Optional(), Length(max=150)])
    fiscal_email = StringField('Correo para Envío de Factura Electrónica', validators=[Optional(), Length(max=150)])

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
