"""TEMPORAL (T016): servicio sonda para verificar el aislamiento (spec HU-4).

Se elimina con probe_items al cerrar la spec 002.
"""

import uuid

from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.errors import DomainValidationError, NotFoundError
from src.models.domain import AuthContext, ProbeItemData
from src.repos.probe_item import ProbeItemRepo
from src.services.auth import REQUIRED_FIELD


async def list_items(db: AsyncSession, context: AuthContext) -> list[ProbeItemData]:
    """Solo los activos de la empresa de la sesión (CA-4.2, principio 4)."""
    return await ProbeItemRepo(db).list_active(context.company_id)


async def get_item(
    db: AsyncSession, context: AuthContext, item_id: uuid.UUID
) -> ProbeItemData:
    """NotFoundError si no existe o es de otra empresa: indistinguibles (RN-9)."""
    item = await ProbeItemRepo(db).get(context.company_id, item_id)
    if item is None:
        raise NotFoundError()
    return item


async def rename_item(
    db: AsyncSession, context: AuthContext, item_id: uuid.UUID, *, name: str
) -> ProbeItemData:
    if not name.strip():
        raise DomainValidationError({"name": REQUIRED_FIELD})
    if not await ProbeItemRepo(db).rename(context.company_id, item_id, name=name):
        # CA-4.4: el de otra empresa no cambia y falla como "no encontrado".
        raise NotFoundError()
    await db.commit()
    return await get_item(db, context, item_id)
