"""Logging estructurado en JSON con request_id y company_id (constitución)."""

import logging
import time
import uuid
from collections.abc import MutableMapping
from typing import Any

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REDACTED = "[REDACTED]"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: REDACTED if "password" in str(k).lower() else _redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_redact(v) for v in value]
    return value


def redact_passwords(
    _: Any, __: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Sustituye el valor de toda clave que contenga "password" (CA-1.6, RN-5)."""
    return dict(_redact(dict(event_dict)))


def configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_passwords,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        # Cada logger se crea al usarse y escribe en el sys.stdout de ese momento.
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def bind_company(company_id: uuid.UUID) -> None:
    """Añade la empresa de la sesión a todas las líneas de la petición en curso."""
    structlog.contextvars.bind_contextvars(company_id=str(company_id))


class RequestLoggingMiddleware:
    """Una línea `request` por petición, con request_id y company_id.

    ASGI puro (no BaseHTTPMiddleware): la petición corre en la misma tarea, así
    que el company_id que fija la dependencia de autenticación llega hasta aquí.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=uuid.uuid4().hex, company_id=None
        )
        estado = {"status_code": 500}
        inicio = time.perf_counter()

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                estado["status_code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            structlog.get_logger().info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status_code=estado["status_code"],
                duration_ms=round((time.perf_counter() - inicio) * 1000, 1),
            )
            structlog.contextvars.clear_contextvars()
