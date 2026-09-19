"""TEMPORAL (T016): /api/v1/_probe, sonda de aislamiento entre empresas.

Se elimina al cerrar la spec 002, cuando existan recursos de negocio reales.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.db import get_db
from src.core.deps import get_auth_context, require_csrf
from src.models.domain import AuthContext, ProbeItemData
from src.models.schemas.probe import ProbeItemList, ProbeItemOut, RenameProbeItem
from src.services import probe

router = APIRouter(prefix="/api/v1/_probe", tags=["probe"])

Db = Annotated[AsyncSession, Depends(get_db)]
Context = Annotated[AuthContext, Depends(get_auth_context)]


def _out(item: ProbeItemData) -> ProbeItemOut:
    return ProbeItemOut(id=item.id, name=item.name)


@router.get("")
async def list_items(context: Context, db: Db) -> ProbeItemList:
    return ProbeItemList(items=[_out(i) for i in await probe.list_items(db, context)])


@router.get("/{item_id}")
async def get_item(item_id: uuid.UUID, context: Context, db: Db) -> ProbeItemOut:
    return _out(await probe.get_item(db, context, item_id))


@router.patch("/{item_id}", dependencies=[Depends(require_csrf)])
async def rename_item(
    item_id: uuid.UUID, body: RenameProbeItem, context: Context, db: Db
) -> ProbeItemOut:
    return _out(await probe.rename_item(db, context, item_id, name=body.name))
