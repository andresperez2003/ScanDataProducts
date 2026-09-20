"""/api/v1/suppliers: traducción HTTP del catálogo de proveedores (plan §5).

Sin lógica de negocio: valida la entrada, obtiene el `company_id` de la sesión y
llama al servicio (constitución, principio 3). El `company_id` nunca se lee de la
ruta, la query ni el cuerpo.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.db import get_db
from src.core.deps import get_auth_context, require_csrf
from src.core.pagination import MAX_PAGE_SIZE
from src.models.domain import AuthContext, SupplierData
from src.models.schemas.catalog import Page, SupplierIn, SupplierOut
from src.services import suppliers

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])

Db = Annotated[AsyncSession, Depends(get_db)]
Context = Annotated[AuthContext, Depends(get_auth_context)]
# D-6: 20 por defecto y como máximo. Pedir más es una petición inválida, no una
# página recortada en silencio.
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]


def _out(proveedor: SupplierData) -> SupplierOut:
    return SupplierOut(
        id=proveedor.id, name=proveedor.name, disabled_at=proveedor.disabled_at
    )


@router.get("")
async def list_suppliers(
    context: Context,
    db: Db,
    search: str | None = None,
    include_disabled: bool = False,
    page: PageNumber = 1,
    page_size: PageSize = MAX_PAGE_SIZE,
) -> Page[SupplierOut]:
    items, total = await suppliers.list_suppliers(
        db,
        context,
        search=search,
        include_disabled=include_disabled,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[_out(s) for s in items], total=total, page=page, page_size=page_size
    )


@router.get("/{supplier_id}")
async def get_supplier(supplier_id: uuid.UUID, context: Context, db: Db) -> SupplierOut:
    return _out(await suppliers.get_supplier(db, context, supplier_id))


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
async def create_supplier(body: SupplierIn, context: Context, db: Db) -> SupplierOut:
    return _out(await suppliers.create_supplier(db, context, name=body.name))


@router.patch("/{supplier_id}", dependencies=[Depends(require_csrf)])
async def update_supplier(
    supplier_id: uuid.UUID, body: SupplierIn, context: Context, db: Db
) -> SupplierOut:
    return _out(
        await suppliers.update_supplier(db, context, supplier_id, name=body.name)
    )


@router.post(
    "/{supplier_id}/disable", status_code=204, dependencies=[Depends(require_csrf)]
)
async def disable_supplier(
    supplier_id: uuid.UUID, context: Context, db: Db
) -> Response:
    await suppliers.disable_supplier(db, context, supplier_id)
    return Response(status_code=204)


@router.post(
    "/{supplier_id}/enable", status_code=204, dependencies=[Depends(require_csrf)]
)
async def enable_supplier(supplier_id: uuid.UUID, context: Context, db: Db) -> Response:
    await suppliers.enable_supplier(db, context, supplier_id)
    return Response(status_code=204)
