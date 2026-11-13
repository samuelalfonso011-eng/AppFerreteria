from flask_wtf import FlaskForm
from wtforms import BooleanField
from wtforms.validators import DataRequired


class PrivacyForm(FlaskForm):
    """Autorización expresa, desmarcada y exigida también sin JavaScript."""
    accept_privacy = BooleanField(
        'Autorizo el tratamiento de mis datos para esta solicitud', default=False,
        validators=[DataRequired(message='Debes autorizar el tratamiento de datos para continuar.')])
