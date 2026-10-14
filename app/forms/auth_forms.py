from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models.user import User


class LoginForm(FlaskForm):
    email = StringField('Correo electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio."),
        Email(check_deliverability=False, message="Introduce un correo electrónico válido.")
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria.")
    ])
    remember = BooleanField('Recordar sesión')
    submit = SubmitField('Iniciar sesión')


class RegisterForm(FlaskForm):
    full_name = StringField('Nombre completo', validators=[
        DataRequired(message="El nombre completo es obligatorio."),
        Length(min=3, max=150, message="El nombre debe tener entre 3 y 150 caracteres.")
    ])
    email = StringField('Correo electrónico', validators=[
        DataRequired(message="El correo electrónico es obligatorio."),
        Email(check_deliverability=False, message="Introduce un correo electrónico válido.")
    ])
    phone = StringField('Teléfono de contacto', validators=[
        Length(max=30, message="El teléfono no puede exceder 30 caracteres.")
    ])
    password = PasswordField('Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria."),
        Length(min=6, message="La contraseña debe tener al menos 6 caracteres.")
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


class ProfileForm(FlaskForm):
    full_name = StringField('Nombre completo', validators=[
        DataRequired(message="El nombre completo es obligatorio."),
        Length(min=3, max=150)
    ])
    phone = StringField('Teléfono de contacto', validators=[
        Length(max=30)
    ])
    submit = SubmitField('Actualizar perfil')


class AddressForm(FlaskForm):
    recipient_name = StringField('Nombre de quien recibe', validators=[
        DataRequired(message="El nombre del destinatario es obligatorio."),
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
        DataRequired(message="La dirección es obligatoria."),
        Length(max=255)
    ])
    complement = StringField('Complemento (Apto, Torre, Oficina)', validators=[
        Length(max=100)
    ])
    delivery_instructions = TextAreaField('Indicaciones adicionales de entrega')
    is_default = BooleanField('Establecer como dirección principal')
    submit = SubmitField('Guardar dirección')
