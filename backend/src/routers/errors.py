"""Traducción de errores a HTTP con el formato único de plan §5."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.errors import (
    DomainError,
    DomainValidationError,
    TooManyAttemptsError,
    http_status_for,
)
from src.services.auth import REQUIRED_FIELD

INVALID_VALUE = "Valor no válido."


def _body(code: str, message: str, fields: dict[str, str]) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "fields": fields}}


def domain_error_response(error: DomainError) -> JSONResponse:
    fields = error.fields if isinstance(error, DomainValidationError) else {}
    headers = (
        {"Retry-After": str(error.retry_after_seconds)}
        if isinstance(error, TooManyAttemptsError)
        else None
    )
    return JSONResponse(
        _body(error.code, error.message, fields),
        status_code=http_status_for(error),
        headers=headers,
    )


async def _handle_domain_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, DomainError)
    return domain_error_response(error)


async def _handle_request_validation(_: Request, error: Exception) -> JSONResponse:
    """Cuerpo mal formado → 400 VALIDATION_ERROR por campo, sin repetir valores."""
    assert isinstance(error, RequestValidationError)
    fields: dict[str, str] = {}
    for detalle in error.errors():
        loc = detalle.get("loc", ())
        campo = str(loc[1]) if len(loc) > 1 else "body"
        fields[campo] = (
            REQUIRED_FIELD if detalle.get("type") == "missing" else INVALID_VALUE
        )
    return domain_error_response(DomainValidationError(fields))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation)
