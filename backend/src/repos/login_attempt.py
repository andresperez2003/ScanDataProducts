from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.domain import LoginAttemptData
from src.models.login_attempt import LoginAttempt


def _to_domain(row: LoginAttempt) -> LoginAttemptData:
    return LoginAttemptData(
        username_normalized=row.username_normalized,
        # asyncpg devuelve INET como objeto ipaddress.
        client_ip=str(row.client_ip),
        succeeded=row.succeeded,
        attempted_at=row.attempted_at,
    )


class LoginAttemptRepo:
    """Acceso a `login_attempts`, que no es tabla de negocio (plan §4).

    Solo lee y escribe: decidir si hay que bloquear es del servicio (T012).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record(
        self, *, username_normalized: str, client_ip: str, succeeded: bool, at: datetime
    ) -> LoginAttemptData:
        row = LoginAttempt(
            username_normalized=username_normalized,
            client_ip=client_ip,
            succeeded=succeeded,
            attempted_at=at,
        )
        self._db.add(row)
        await self._db.flush()
        return LoginAttemptData(
            username_normalized=username_normalized,
            client_ip=client_ip,
            succeeded=succeeded,
            attempted_at=at,
        )

    async def recent_by_username(
        self, username_normalized: str, *, since: datetime
    ) -> list[LoginAttemptData]:
        """Intentos de ese usuario desde `since`, del más antiguo al más reciente."""
        return await self._recent(
            col(LoginAttempt.username_normalized) == username_normalized, since
        )

    async def recent_by_ip(
        self, client_ip: str, *, since: datetime
    ) -> list[LoginAttemptData]:
        """Intentos desde ese origen desde `since`, del más antiguo al más reciente."""
        return await self._recent(col(LoginAttempt.client_ip) == client_ip, since)

    async def _recent(
        self, filtro: ColumnElement[bool], since: datetime
    ) -> list[LoginAttemptData]:
        consulta = (
            select(LoginAttempt)
            .where(filtro, col(LoginAttempt.attempted_at) >= since)
            .order_by(col(LoginAttempt.attempted_at))
        )
        filas: Sequence[LoginAttempt] = (await self._db.exec(consulta)).all()
        return [_to_domain(fila) for fila in filas]
