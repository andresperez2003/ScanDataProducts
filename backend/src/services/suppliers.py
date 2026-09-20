"""Reglas de negocio del catálogo de proveedores (spec HU-1, HU-2, RN-1, RN-6).

No importa `fastapi`: lanza excepciones de dominio y el router las traduce
(constitución, principios 3 y 5).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.errors import (
    DomainValidationError,
    DuplicateSupplierNameError,
    NotFoundError,
)
from src.core.normalize import normalize_name
from src.core.pagination import MAX_PAGE_SIZE
from src.models.domain import AuthContext, SupplierData
from src.repos.supplier import SupplierPage, SupplierRepo
from src.services.auth import REQUIRED_FIELD


def _validated_name(name: str) -> str:
    """El nombre normalizado, o error por campo si está vacío (CA-1.3).

    Un nombre de solo espacios cuenta como vacío: normalizar lo deja en "".
    """
    normalizado = normalize_name(name)
    if not normalizado:
        raise DomainValidationError({"name": REQUIRED_FIELD})
    return normalizado


async def list_suppliers(
    db: AsyncSession,
    context: AuthContext,
    *,
    search: str | None = None,
    include_disabled: bool = False,
    page: int = 1,
    page_size: int = MAX_PAGE_SIZE,
) -> SupplierPage:
    """Una página del catálogo de la empresa de la sesión (CA-2.1 a CA-2.4).

    El término se normaliza igual que los nombres almacenados, así la búsqueda
    no distingue mayúsculas ni espacios sobrantes (CA-2.2). Buscar con el campo
    vacío equivale a listar (§5, séptimo caso borde).
    """
    termino = normalize_name(search) if search else None
    return await SupplierRepo(db).list(
        context.company_id,
        search=termino or None,
        include_disabled=include_disabled,
        page=page,
        page_size=page_size,
    )


async def get_supplier(
    db: AsyncSession, context: AuthContext, supplier_id: uuid.UUID
) -> SupplierData:
    """NotFoundError si no existe o es de otra empresa: indistinguibles (RN-8)."""
    proveedor = await SupplierRepo(db).get(context.company_id, supplier_id)
    if proveedor is None:
        raise NotFoundError()
    return proveedor


async def create_supplier(
    db: AsyncSession, context: AuthContext, *, name: str
) -> SupplierData:
    """Alta de un proveedor activo (CA-1.1).

    El duplicado lo detecta el índice único parcial, también bajo concurrencia
    (§5, tercer caso borde): la violación se traduce a error de dominio, nunca
    a un 500.
    """
    normalizado = _validated_name(name)
    try:
        proveedor = await SupplierRepo(db).create(
            context.company_id,
            name=name,
            name_normalized=normalizado,
            created_by=context.user_id,
        )
    except IntegrityError:
        await db.rollback()
        raise DuplicateSupplierNameError() from None
    await db.commit()
    return proveedor


async def update_supplier(
    db: AsyncSession, context: AuthContext, supplier_id: uuid.UUID, *, name: str
) -> SupplierData:
    """Cambia el nombre (CA-1.4). CA-1.5: si choca, el original no cambia."""
    normalizado = _validated_name(name)
    repo = SupplierRepo(db)
    # Comprobar antes de escribir: un id de otra empresa debe fallar como
    # "no encontrado", no como duplicado (RN-8, CA-5.4).
    await get_supplier(db, context, supplier_id)
    try:
        await repo.update(
            context.company_id, supplier_id, name=name, name_normalized=normalizado
        )
    except IntegrityError:
        await db.rollback()
        raise DuplicateSupplierNameError() from None
    await db.commit()
    return await get_supplier(db, context, supplier_id)


async def disable_supplier(
    db: AsyncSession, context: AuthContext, supplier_id: uuid.UUID
) -> None:
    """Deshabilita el proveedor (CA-1.6, RN-6). Nunca borra.

    Deshabilitar uno ya deshabilitado no es un error: el estado final es el
    pedido. No toca los productos que ya lo referencian (D-3, RN-5).
    """
    await get_supplier(db, context, supplier_id)
    await SupplierRepo(db).disable(
        context.company_id,
        supplier_id,
        disabled_by=context.user_id,
        at=datetime.now(UTC),
    )
    await db.commit()


async def enable_supplier(
    db: AsyncSession, context: AuthContext, supplier_id: uuid.UUID
) -> None:
    """Rehabilita el proveedor (CA-1.8).

    CA-1.7 y D-4: si su nombre ya lo usa un proveedor activo, se rechaza igual
    que un alta duplicada. Lo decide el mismo índice único parcial, al dejar de
    estar la fila fuera de él.
    """
    await get_supplier(db, context, supplier_id)
    try:
        await SupplierRepo(db).enable(context.company_id, supplier_id)
    except IntegrityError:
        await db.rollback()
        raise DuplicateSupplierNameError() from None
    await db.commit()
