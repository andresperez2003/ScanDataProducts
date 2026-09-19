"""Política de contraseñas: spec RN-4 (D-5)."""

import string
from enum import Enum

from src.core.errors import DomainValidationError

MIN_LENGTH = 12
SPECIAL_CHARACTERS = frozenset("#$%&*_@")
_UPPERCASE = frozenset(string.ascii_uppercase)
_LOWERCASE = frozenset(string.ascii_lowercase)
_DIGITS = frozenset(string.digits)
# Solo ASCII: ni espacios, ni ñ, ni acentos, ni otros símbolos (D-5).
_ALLOWED = _UPPERCASE | _LOWERCASE | _DIGITS | SPECIAL_CHARACTERS


class PasswordRequirement(Enum):
    """Cada requisito de RN-4, con el texto que ve el usuario (CA-1.4)."""

    MIN_LENGTH = f"Debe tener al menos {MIN_LENGTH} caracteres."
    UPPERCASE = "Debe incluir al menos una letra mayúscula (A-Z)."
    LOWERCASE = "Debe incluir al menos una letra minúscula (a-z)."
    DIGIT = "Debe incluir al menos un número (0-9)."
    SPECIAL = "Debe incluir al menos uno de estos caracteres: # $ % & * _ @"
    ALLOWED_CHARACTERS = (
        "Solo puede contener letras sin acentos ni ñ, números y # $ % & * _ @ "
        "(sin espacios)."
    )

    @property
    def message(self) -> str:
        return str(self.value)


def check_password(password: str) -> list[PasswordRequirement]:
    """Requisitos que incumple, en orden fijo. Lista vacía = válida.

    Nunca modifica la contraseña: no recorta espacios ni normaliza.
    """
    caracteres = set(password)
    incumplidos = [
        (len(password) < MIN_LENGTH, PasswordRequirement.MIN_LENGTH),
        (not caracteres & _UPPERCASE, PasswordRequirement.UPPERCASE),
        (not caracteres & _LOWERCASE, PasswordRequirement.LOWERCASE),
        (not caracteres & _DIGITS, PasswordRequirement.DIGIT),
        (not caracteres & SPECIAL_CHARACTERS, PasswordRequirement.SPECIAL),
        (not caracteres <= _ALLOWED, PasswordRequirement.ALLOWED_CHARACTERS),
    ]
    return [requisito for falla, requisito in incumplidos if falla]


def validate_password(password: str) -> None:
    """Lanza DomainValidationError con cada requisito incumplido en `password`."""
    incumplidos = check_password(password)
    if incumplidos:
        raise DomainValidationError(
            {"password": " ".join(r.message for r in incumplidos)}
        )
