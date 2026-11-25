"""Validacion y saneamiento de entradas JSON. Toda entrada se trata como no confiable."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

REQUIRED = "Este campo es obligatorio."


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("validation")
        self.errors = errors


def clean_text(value, multiline=False):
    value = unicodedata.normalize("NFC", value)
    value = CONTROL_CHARS.sub("", value)
    if multiline:
        lines = [" ".join(line.split()) for line in value.replace("\r\n", "\n").split("\n")]
        return "\n".join(lines).strip()
    return " ".join(value.split())


def valid_email(value):
    local = value.partition("@")[0]
    return (len(value) <= 254 and bool(EMAIL_RE.fullmatch(value))
            and not local.startswith(".") and not local.endswith(".") and ".." not in local)


def slugify(text, max_len=200):
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:max_len].strip("-") or "item"


class Validator:
    """Acumula errores por campo para devolverlos todos juntos al frontend."""

    def __init__(self, data):
        self.data = data if isinstance(data, dict) else {}
        self.errors = {}

    def _missing(self, raw):
        return raw is None or (isinstance(raw, str) and not raw.strip())

    def text(self, field, max_len, min_len=1, required=True, multiline=False, pattern=None,
             pattern_msg="El formato no es válido."):
        raw = self.data.get(field)
        if self._missing(raw):
            if required:
                self.errors[field] = REQUIRED
            return None
        if not isinstance(raw, str):
            self.errors[field] = "El valor no es válido."
            return None
        value = clean_text(raw, multiline)
        if len(value) < min_len:
            self.errors[field] = f"Escribe al menos {min_len} caracteres."
        elif len(value) > max_len:
            self.errors[field] = f"Usa como máximo {max_len} caracteres."
        elif pattern is not None and not pattern.fullmatch(value):
            self.errors[field] = pattern_msg
        return value

    def email(self, field, required=True):
        raw = self.data.get(field)
        if self._missing(raw):
            if required:
                self.error(field, REQUIRED)
            return None
        value = raw.strip().lower() if isinstance(raw, str) else ""
        if not valid_email(value):
            self.error(field, "Escribe un correo válido, por ejemplo nombre@dominio.com.")
        return value

    def integer(self, field, min_value, max_value, required=True, default=None):
        raw = self.data.get(field)
        if self._missing(raw):
            if required:
                self.errors[field] = REQUIRED
            return default
        if isinstance(raw, bool):
            self.errors[field] = "Debe ser un número entero."
            return default
        try:
            value = int(raw) if isinstance(raw, (int, str)) else None
            if isinstance(raw, str) and not raw.strip().lstrip("-").isdigit():
                value = None
        except (TypeError, ValueError):
            value = None
        if value is None:
            self.errors[field] = "Debe ser un número entero."
            return default
        if not min_value <= value <= max_value:
            self.errors[field] = f"Debe estar entre {min_value} y {max_value}."
        return value

    def money(self, field, min_value=0, max_value=10_000_000_000, required=True):
        raw = self.data.get(field)
        if self._missing(raw):
            if required:
                self.errors[field] = REQUIRED
            return None
        if isinstance(raw, bool):
            self.errors[field] = "Escribe un valor numérico."
            return None
        try:
            value = Decimal(str(raw).strip())
        except (InvalidOperation, ValueError):
            self.errors[field] = "Escribe un valor numérico."
            return None
        if not value.is_finite() or value < min_value or value > max_value:
            self.errors[field] = "El valor está fuera del rango permitido."
            return None
        return value.quantize(Decimal("0.01"))

    def boolean(self, field, default=False):
        raw = self.data.get(field, default)
        if not isinstance(raw, bool):
            self.errors[field] = "El valor no es válido."
            return default
        return raw

    def choice(self, field, choices, required=True, default=None):
        raw = self.data.get(field)
        if self._missing(raw):
            if required:
                self.errors[field] = "Elige una opción."
            return default
        if raw not in choices:
            self.errors[field] = "Elige una opción válida."
            return default
        return raw

    def accepted(self, field, message):
        if self.data.get(field) is not True:
            self.errors[field] = message
            return False
        return True

    def error(self, field, message):
        self.errors[field] = message

    def raise_if_errors(self):
        if self.errors:
            raise ValidationError(self.errors)
