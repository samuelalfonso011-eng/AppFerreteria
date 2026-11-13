"""Validación de escalares sin coerciones silenciosas desde JSON."""
import re


def strict_integer(value, *, minimum: int = 0, maximum: int = 2_147_483_647) -> int:
    if type(value) is int:
        result = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]{1,10}", value):
        result = int(value)
    else:
        raise ValueError("Se requiere un número entero válido.")
    if not minimum <= result <= maximum:
        raise ValueError("El número está fuera del rango permitido.")
    return result
