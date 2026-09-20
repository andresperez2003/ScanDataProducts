"""/api/v1/products: traducción HTTP del catálogo de productos (plan §5).

Sin lógica de negocio: valida la entrada, obtiene el `company_id` de la sesión y
llama al servicio (constitución, principio 3). El `company_id` nunca se lee de la
ruta, la query ni el cuerpo; `supplier_id` sí, porque es un dato del producto, y
el servicio comprueba que sea de la empresa de la sesión.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.db import get_db
from src.core.deps import get_auth_context, require_csrf
from src.core.pagination import MAX_PAGE_SIZE
from src.models.domain import AuthContext, ProductData
from src.models.schemas.catalog import Page, ProductIn, ProductOut, SupplierOut
from src.services import products

router = APIRouter(prefix="/api/v1/products", tags=["products"])

Db = Annotated[AsyncSession, Depends(get_db)]
Context = Annotated[AuthContext, Depends(get_auth_context)]
# D-6: 20 por defecto y como máximo. Pedir más es una petición inválida, no una
# página recortada en silencio.
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]


def _out(producto: ProductData) -> ProductOut:
    proveedor = producto.supplier
    return ProductOut(
        id=producto.id,
        name=producto.name,
        sku=producto.sku,
        # El proveedor va embebido, nunca como un id suelto (§7, "consistencia").
        supplier=(
            None
            if proveedor is None
            else SupplierOut(
                id=proveedor.id, name=proveedor.name, disabled_at=proveedor.disabled_at
            )
        ),
        disabled_at=producto.disabled_at,
    )


@router.get("")
async def list_products(
    context: Context,
    db: Db,
    search: str | None = None,
    supplier_id: uuid.UUID | None = None,
    include_disabled: bool = False,
    page: PageNumber = 1,
    page_size: PageSize = MAX_PAGE_SIZE,
) -> Page[ProductOut]:
    items, total = await products.list_products(
        db,
        context,
        search=search,
        supplier_id=supplier_id,
        include_disabled=include_disabled,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[_out(p) for p in items], total=total, page=page, page_size=page_size
    )


@router.get("/{product_id}")
async def get_product(product_id: uuid.UUID, context: Context, db: Db) -> ProductOut:
    return _out(await products.get_product(db, context, product_id))


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
async def create_product(body: ProductIn, context: Context, db: Db) -> ProductOut:
    return _out(
        await products.create_product(
            db, context, name=body.name, sku=body.sku, supplier_id=body.supplier_id
        )
    )


@router.patch("/{product_id}", dependencies=[Depends(require_csrf)])
async def update_product(
    product_id: uuid.UUID, body: ProductIn, context: Context, db: Db
) -> ProductOut:
    return _out(
        await products.update_product(
            db,
            context,
            product_id,
            name=body.name,
            sku=body.sku,
            supplier_id=body.supplier_id,
        )
    )


@router.post(
    "/{product_id}/disable", status_code=204, dependencies=[Depends(require_csrf)]
)
async def disable_product(product_id: uuid.UUID, context: Context, db: Db) -> Response:
    await products.disable_product(db, context, product_id)
    return Response(status_code=204)


@router.post(
    "/{product_id}/enable", status_code=204, dependencies=[Depends(require_csrf)]
)
async def enable_product(product_id: uuid.UUID, context: Context, db: Db) -> Response:
    await products.enable_product(db, context, product_id)
    return Response(status_code=204)
