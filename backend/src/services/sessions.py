"""Ciclo de vida de la sesión de servidor (plan §4, tabla `sessions`)."""

from datetime import datetime, timedelta

from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import get_settings
from src.core.errors import NotAuthenticatedError
from src.core.security import generate_session_token, hash_session_token
from src.models.domain import AuthContext, SessionData, UserData
from src.repos.session import SessionRepo
from src.repos.user import UserRepo


async def start_session(db: AsyncSession, user: UserData, *, now: datetime) -> str:
    """Crea la sesión y devuelve el token en claro, que solo viaja en la cookie.

    En la BD queda su SHA-256. La caducidad absoluta se fija al crearla (D-3).
    No confirma la transacción: lo hace quien llama.
    """
    token = generate_session_token()
    await SessionRepo(db).create(
        user.company_id,
        user_id=user.id,
        token_hash=hash_session_token(token),
        created_at=now,
        absolute_expires_at=now + timedelta(days=get_settings().session_max_age_days),
    )
    return token


def _expired(session: SessionData, now: datetime) -> bool:
    inactividad = timedelta(hours=get_settings().session_timeout_hours)
    return (
        now >= session.absolute_expires_at  # D-3, CA-3.5
        or now - session.last_seen_at >= inactividad  # CA-3.3
    )


async def _valid_session(db: AsyncSession, token: str, now: datetime) -> SessionData:
    """La sesión del token si sigue siendo utilizable; si no, NotAuthenticatedError."""
    session = await SessionRepo(db).get_active_by_token_hash(hash_session_token(token))
    if session is None or _expired(session, now):
        raise NotAuthenticatedError()
    user = await UserRepo(db).get(session.company_id, session.user_id)
    # RN-7: el usuario deshabilitado pierde sus sesiones en la siguiente petición.
    if user is None or user.disabled_at is not None:
        raise NotAuthenticatedError()
    return session


async def resolve_session(
    db: AsyncSession, token: str, *, now: datetime
) -> AuthContext:
    """Valida la sesión de una petición y renueva su actividad (CA-3.1, CA-3.3).

    Rechaza sesiones desconocidas, revocadas (CA-3.2), inactivas 8 h (CA-3.3),
    con 15 días desde su creación (CA-3.5) o de usuarios deshabilitados (RN-7).
    """
    session = await _valid_session(db, token, now)
    await SessionRepo(db).touch(session.id, at=now)
    await db.commit()
    return AuthContext(
        user_id=session.user_id,
        company_id=session.company_id,
        session_id=session.id,
    )


async def end_session(db: AsyncSession, token: str, *, now: datetime) -> None:
    """Cierre de sesión: la revoca para siempre (CA-3.2). Exige sesión válida."""
    session = await _valid_session(db, token, now)
    await SessionRepo(db).revoke(session.id, at=now)
    await db.commit()
