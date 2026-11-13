from app.forms.privacy import PrivacyForm
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField, HiddenField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models.user import User


class LoginForm(FlaskForm):
    email = StringField('Correo electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio."),
        Email(check_deliverability=False, message="Introduce un correo electrónico válido."),
        Length(max=255)
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria."), Length(max=128)
    ])
    remember = BooleanField('Recordar sesión')
    submit = SubmitField('Iniciar sesión')


class RegisterForm(PrivacyForm):
    accept_terms = BooleanField("Acepto los términos y condiciones", default=False,
        validators=[DataRequired(message="Debes aceptar los términos y condiciones.")])
    full_name = StringField('Nombre completo', validators=[
        DataRequired(message="El nombre completo es obligatorio."),
        Length(min=3, max=150, message="El nombre debe tener entre 3 y 150 caracteres.")
    ])
    email = StringField('Correo electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio."),
        Email(check_deliverability=False, message="Introduce un correo electrónico válido."),
        Length(max=255)
    ])
    phone = StringField('Teléfono de contacto', validators=[
        Length(max=30, message="El teléfono no puede exceder 30 caracteres.")
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria."),
        Length(min=12, max=128, message="La contraseña debe tener entre 12 y 128 caracteres.")
    ])
    confirm_password = PasswordField('Confirmar contraseña', validators=[
        DataRequired(message="Por favor confirma tu contraseña."),
        EqualTo('password', message="Las contraseñas no coinciden.")
    ])
    submit = SubmitField('Crear cuenta')

    def validate_email(self, field):
        normalized = field.data.strip().lower()
        if User.query.filter_by(email=normalized).first():
            raise ValidationError("Este correo electrónico ya se encuentra registrado.")


class ProfileForm(PrivacyForm):
    full_name = StringField('Nombre completo', validators=[
        DataRequired(message="El nombre completo es obligatorio."),
        Length(min=3, max=150)
    ])
    phone = StringField('Teléfono de contacto', validators=[
        Length(max=30)
    ])
    submit = SubmitField('Actualizar perfil')


class AddressForm(PrivacyForm):
    recipient_name = StringField('Nombre de quien recibe', validators=[
        DataRequired(message="El nombre del destinatario es obligatorio."),
        Length(max=150)
    ])
    phone = StringField('Teléfono celular de contacto', validators=[
        DataRequired(message="El teléfono es obligatorio."),
        Length(max=30)
    ])
    department = HiddenField('Departamento o Región', default='Antioquia')
    city = SelectField('Municipio (Valle de Aburrá)', choices=[
        ('Medellín', 'Medellín'),
        ('Bello', 'Bello'),
        ('Itagüí', 'Itagüí'),
        ('Envigado', 'Envigado'),
        ('Sabaneta', 'Sabaneta'),
        ('Copacabana', 'Copacabana'),
        ('La Estrella', 'La Estrella'),
        ('Girardota', 'Girardota'),
        ('Caldas', 'Caldas'),
        ('Barbosa', 'Barbosa')
    ], default='Medellín', validators=[
        DataRequired(message="Selecciona un municipio del Valle de Aburrá.")
    ])
    neighborhood = StringField('Barrio o Sector', validators=[
        DataRequired(message="El barrio es obligatorio."),
        Length(max=100)
    ])
    street_address = StringField('Dirección exacta de entrega', validators=[
        DataRequired(message="La dirección es obligatoria."),
        Length(max=255)
    ])
    complement = StringField('Interior / Apto / Bodega / Obra', validators=[
        Length(max=100)
    ])
    delivery_instructions = TextAreaField('Indicaciones de entrega para el conductor', validators=[Length(max=500)])
    is_default = BooleanField('Establecer como dirección principal')
    submit = SubmitField('Guardar dirección')


class ForgotPasswordForm(FlaskForm):
    """Formulario para solicitar restablecimiento de contraseña."""
    email = StringField('Correo electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio."),
        Email(check_deliverability=False, message="Introduce un correo electrónico válido."),
        Length(max=255)
    ])
    submit = SubmitField('Enviar enlace de recuperación')


class ResetPasswordForm(FlaskForm):
    """Formulario para definir una nueva contraseña con token firmado."""
    password = PasswordField('Nueva contraseña', validators=[
        DataRequired(message="La nueva contraseña es obligatoria."),
        Length(min=12, max=128, message="La contraseña debe tener entre 12 y 128 caracteres.")
    ])
    confirm_password = PasswordField('Confirmar nueva contraseña', validators=[
        DataRequired(message="Por favor confirma la nueva contraseña."),
        EqualTo('password', message="Las contraseñas no coinciden.")
    ])
    submit = SubmitField('Guardar nueva contraseña')

