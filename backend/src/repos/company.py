import uuid

from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.company import Company
from src.models.domain import CompanyData


def _to_domain(row: Company) -> CompanyData:
    return CompanyData(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        disabled_at=row.disabled_at,
    )


class CompanyRepo:
    """Acceso a `companies`. Hace flush, nunca commit: la transacción es del servicio."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self, company_id: uuid.UUID, *, name: str, name_normalized: str
    ) -> CompanyData:
        row = Company(id=company_id, name=name, name_normalized=name_normalized)
        self._db.add(row)
        await self._db.flush()
        # created_at lo pone la BD (server_default).
        await self._db.refresh(row)
        return _to_domain(row)

    async def get(self, company_id: uuid.UUID) -> CompanyData | None:
        row = await self._db.get(Company, company_id)
        return _to_domain(row) if row is not None else None
