"""Dependencias de FastAPI compartidas por los routers."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, is_valid_csrf
from src.core.db import get_db
from src.core.errors import CsrfFailedError, NotAuthenticatedError
from src.core.logging import bind_company
from src.core.security import unsign_session_token
from src.models.domain import AuthContext
from src.services.sessions import resolve_session

SESSION_COOKIE_NAME = "session"


def get_session_token(request: Request) -> str:
    """Token en claro de la cookie `session`, si su firma es válida."""
    firmado = request.cookies.get(SESSION_COOKIE_NAME)
    token = unsign_session_token(firmado) if firmado else None
    if token is None:
        raise NotAuthenticatedError()
    return token


async def get_auth_context(
    token: Annotated[str, Depends(get_session_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext:
    """Única forma de obtener el company_id: sale de la sesión, nunca del cliente."""
    context = await resolve_session(db, token, now=datetime.now(UTC))
    bind_company(context.company_id)
    return context


def require_csrf(request: Request) -> None:
    """Double-submit para toda operación que modifica estado (spec §7)."""
    if not is_valid_csrf(
        cookie_value=request.cookies.get(CSRF_COOKIE_NAME),
        header_value=request.headers.get(CSRF_HEADER_NAME),
    ):
        raise CsrfFailedError()
