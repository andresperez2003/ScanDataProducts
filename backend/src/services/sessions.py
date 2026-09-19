"""Ciclo de vida de la sesión de servidor (plan §4, tabla `sessions`)."""

from datetime import datetime, timedelta

from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import get_settings
from src.core.security import generate_session_token, hash_session_token
from src.models.domain import UserData
from src.repos.session import SessionRepo


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
