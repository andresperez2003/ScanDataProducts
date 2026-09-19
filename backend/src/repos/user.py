import uuid
from datetime import datetime

from sqlmodel import col, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.domain import UserData
from src.models.user import User


def _to_domain(row: User) -> UserData:
    return UserData(
        id=row.id,
        company_id=row.company_id,
        username=row.username,
        password_hash=row.password_hash,
        created_at=row.created_at,
        disabled_at=row.disabled_at,
    )


class UserRepo:
    """Acceso a `users`. Hace flush, nunca commit: la transacción es del servicio."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        company_id: uuid.UUID,
        *,
        username: str,
        username_normalized: str,
        password_hash: str,
        created_by: uuid.UUID | None,
    ) -> UserData:
        row = User(
            company_id=company_id,
            username=username,
            username_normalized=username_normalized,
            password_hash=password_hash,
            created_by=created_by,
        )
        self._db.add(row)
        await self._db.flush()
        # created_at lo pone la BD (server_default).
        await self._db.refresh(row)
        return _to_domain(row)

    async def get(self, company_id: uuid.UUID, user_id: uuid.UUID) -> UserData | None:
        consulta = select(User).where(User.company_id == company_id, User.id == user_id)
        row = (await self._db.exec(consulta)).first()
        return _to_domain(row) if row is not None else None

    async def get_by_username(self, username_normalized: str) -> UserData | None:
        # EXCEPCIÓN: ver plan.md §3
        # Única consulta sin company_id: el login es lo que determina la empresa.
        # No copiar este patrón en otras features.
        consulta = select(User).where(User.username_normalized == username_normalized)
        row = (await self._db.exec(consulta)).first()
        return _to_domain(row) if row is not None else None

    async def disable(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        disabled_by: uuid.UUID,
        at: datetime,
    ) -> bool:
        """Marca `disabled_at` (nunca borra). False si no existe en esa empresa."""
        consulta = (
            update(User)
            .where(
                col(User.company_id) == company_id,
                col(User.id) == user_id,
                col(User.disabled_at).is_(None),
            )
            .values(disabled_at=at, disabled_by=disabled_by)
        )
        resultado = await self._db.exec(consulta)
        # Las filas ya cargadas en la sesión deben releerse tras el UPDATE.
        self._db.expire_all()
        return resultado.rowcount == 1
