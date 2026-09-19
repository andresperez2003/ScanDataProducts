"""TEMPORAL (T016): se elimina con probe_items al cerrar la spec 002."""

import uuid

from sqlmodel import col, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.domain import ProbeItemData
from src.models.probe_item import ProbeItem


def _to_domain(row: ProbeItem) -> ProbeItemData:
    return ProbeItemData(
        id=row.id,
        company_id=row.company_id,
        name=row.name,
        disabled_at=row.disabled_at,
    )


class ProbeItemRepo:
    """Acceso a `probe_items`. Hace flush, nunca commit."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self, company_id: uuid.UUID, *, name: str, created_by: uuid.UUID
    ) -> ProbeItemData:
        row = ProbeItem(company_id=company_id, name=name, created_by=created_by)
        self._db.add(row)
        await self._db.flush()
        return _to_domain(row)

    async def list_active(self, company_id: uuid.UUID) -> list[ProbeItemData]:
        consulta = (
            select(ProbeItem)
            .where(
                ProbeItem.company_id == company_id,
                col(ProbeItem.disabled_at).is_(None),
            )
            .order_by(col(ProbeItem.created_at), col(ProbeItem.id))
        )
        return [_to_domain(fila) for fila in (await self._db.exec(consulta)).all()]

    async def get(
        self, company_id: uuid.UUID, item_id: uuid.UUID
    ) -> ProbeItemData | None:
        consulta = select(ProbeItem).where(
            ProbeItem.company_id == company_id, ProbeItem.id == item_id
        )
        row = (await self._db.exec(consulta)).first()
        return _to_domain(row) if row is not None else None

    async def rename(
        self, company_id: uuid.UUID, item_id: uuid.UUID, *, name: str
    ) -> bool:
        """False si el elemento no existe en esa empresa (CA-4.4)."""
        consulta = (
            update(ProbeItem)
            .where(
                col(ProbeItem.company_id) == company_id, col(ProbeItem.id) == item_id
            )
            .values(name=name)
        )
        resultado = await self._db.exec(consulta)
        # Las filas ya cargadas en la sesión deben releerse tras el UPDATE.
        self._db.expire_all()
        return resultado.rowcount == 1
