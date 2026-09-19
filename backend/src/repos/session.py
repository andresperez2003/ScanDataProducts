import uuid
from datetime import datetime

from sqlmodel import col, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.domain import SessionData
from src.models.session import Session


def _to_domain(row: Session) -> SessionData:
    return SessionData(
        id=row.id,
        user_id=row.user_id,
        company_id=row.company_id,
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
        absolute_expires_at=row.absolute_expires_at,
        revoked_at=row.revoked_at,
    )


class SessionRepo:
    """Acceso a `sessions`, que no es tabla de negocio (plan §4).

    La búsqueda por token no lleva company_id porque es precisamente lo que
    determina la empresa de la petición. Hace flush, nunca commit.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        company_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        token_hash: bytes,
        created_at: datetime,
        absolute_expires_at: datetime,
    ) -> SessionData:
        row = Session(
            company_id=company_id,
            user_id=user_id,
            token_hash=token_hash,
            created_at=created_at,
            last_seen_at=created_at,
            absolute_expires_at=absolute_expires_at,
        )
        self._db.add(row)
        await self._db.flush()
        return _to_domain(row)

    async def get_active_by_token_hash(self, token_hash: bytes) -> SessionData | None:
        """Sesión no revocada con ese hash. La caducidad la decide el servicio."""
        consulta = select(Session).where(
            Session.token_hash == token_hash, col(Session.revoked_at).is_(None)
        )
        row = (await self._db.exec(consulta)).first()
        return _to_domain(row) if row is not None else None

    async def touch(self, session_id: uuid.UUID, *, at: datetime) -> None:
        await self._update(session_id, last_seen_at=at)

    async def revoke(self, session_id: uuid.UUID, *, at: datetime) -> None:
        await self._update(session_id, revoked_at=at)

    async def _update(self, session_id: uuid.UUID, **values: datetime) -> None:
        consulta = update(Session).where(col(Session.id) == session_id).values(**values)
        await self._db.exec(consulta)
        # Las filas ya cargadas en la sesión deben releerse tras el UPDATE.
        self._db.expire_all()
