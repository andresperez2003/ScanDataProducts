"""Errores de dominio y su único mapeo a HTTP (constitución, principio 5).

Los servicios lanzan estas excepciones; solo los routers las traducen a HTTP.
Este módulo no importa fastapi: lo usan los servicios.
"""

from http import HTTPStatus
from typing import ClassVar


class DomainError(Exception):
    """Base común. `code` y `message` son los del contrato de error (plan §5)."""

    code: ClassVar[str] = ""
    default_message: ClassVar[str] = ""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class DomainValidationError(DomainError):
    """Entrada inválida, con el detalle por campo (CA-1.3, CA-1.4)."""

    code = "VALIDATION_ERROR"
    default_message = "Hay datos que corregir."

    def __init__(self, fields: dict[str, str]) -> None:
        super().__init__()
        self.fields = fields


class DuplicateCompanyError(DomainError):
    """RN-2, CA-1.2."""

    code = "COMPANY_NAME_TAKEN"
    default_message = "Ese nombre de empresa ya está en uso."


class InvalidCredentialsError(DomainError):
    """Mensaje único sea cual sea la causa (RN-6, CA-2.2 a CA-2.4)."""

    code = "INVALID_CREDENTIALS"
    default_message = "Usuario o contraseña incorrectos."

    def __init__(self) -> None:
        # Sin mensaje propio a propósito: ninguna causa puede llegar al cliente.
        super().__init__()


class TooManyAttemptsError(DomainError):
    """CA-2.5, CA-2.6. `retry_after_seconds` alimenta la cabecera Retry-After."""

    code = "TOO_MANY_ATTEMPTS"
    default_message = "Demasiados intentos. Vuelve a intentarlo más tarde."

    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__()
        self.retry_after_seconds = retry_after_seconds


class NotAuthenticatedError(DomainError):
    """Sin sesión, caducada, revocada o de un usuario deshabilitado (CA-3.2 a 3.5)."""

    code = "NOT_AUTHENTICATED"
    default_message = "Inicia sesión para continuar."


# Único lugar donde cada excepción de dominio se asocia a un estado HTTP.
HTTP_STATUS: dict[type[DomainError], int] = {
    DomainValidationError: HTTPStatus.BAD_REQUEST,
    DuplicateCompanyError: HTTPStatus.CONFLICT,
    InvalidCredentialsError: HTTPStatus.UNAUTHORIZED,
    TooManyAttemptsError: HTTPStatus.TOO_MANY_REQUESTS,
    NotAuthenticatedError: HTTPStatus.UNAUTHORIZED,
}


def http_status_for(error: DomainError) -> int:
    return HTTP_STATUS[type(error)]
