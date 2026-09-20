"""Reglas de negocio del catálogo de productos (spec HU-3, HU-4, RN-2 a RN-6).

No importa `fastapi`: lanza excepciones de dominio y el router las traduce
(constitución, principios 3 y 5).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.errors import (
    DomainValidationError,
    DuplicateProductNameError,
    DuplicateProductSkuError,
    NotFoundError,
)
from src.core.normalize import normalize_name
from src.core.pagination import MAX_PAGE_SIZE
from src.models.domain import AuthContext, ProductData
from src.repos.product import ProductPage, ProductRepo
from src.repos.supplier import SupplierRepo
from src.services.auth import REQUIRED_FIELD

SUPPLIER_DISABLED = "Ese proveedor está deshabilitado."

# Los dos índices únicos parciales de `products` (plan §4). El nombre del índice
# violado es lo único que distingue un choque de nombre de uno de SKU.
_NAME_INDEX = "ux_products_company_supplier_name_active"
_SKU_INDEX = "ux_products_company_supplier_sku_active"


def _duplicate_error(
    error: IntegrityError,
) -> DuplicateProductNameError | DuplicateProductSkuError:
    """Traduce la violación del índice a su error de dominio (RN-2, RN-3).

    Si la restricción no es ninguna de las dos previstas, el error se relanza:
    un fallo no contemplado no se disfraza de conflicto (constitución, §5).
    """
    detalle = str(error)
    if _SKU_INDEX in detalle:
        return DuplicateProductSkuError()
    if _NAME_INDEX in detalle:
        return DuplicateProductNameError()
    raise error


def _validated_name(name: str) -> str:
    """El nombre normalizado, o error por campo si está vacío (CA-3.4)."""
    normalizado = normalize_name(name)
    if not normalizado:
        raise DomainValidationError({"name": REQUIRED_FIELD})
    return normalizado


def _normalized_sku(sku: str | None) -> tuple[str | None, str | None]:
    """(sku, sku_normalized). Un SKU en blanco es ausencia de SKU (§5).

    Devolver `None` en ambos deja la fila fuera del índice único de SKU, que es
    lo que permite que dos productos del mismo proveedor no tengan código.
    """
    normalizado = normalize_name(sku) if sku else ""
    return (sku, normalizado) if normalizado else (None, None)


async def _check_supplier(
    db: AsyncSession, context: AuthContext, supplier_id: uuid.UUID | None
) -> None:
    """RN-4 y CA-3.6: el proveedor debe ser mío y estar activo al asignarlo.

    Un proveedor inexistente o de otra empresa es "no encontrado", indistinguible
    entre sí (RN-8). Solo un proveedor propio y deshabilitado da un error por
    campo: decir "está deshabilitado" de uno ajeno revelaría que existe.
    """
    if supplier_id is None:
        return
    proveedor = await SupplierRepo(db).get(context.company_id, supplier_id)
    if proveedor is None:
        raise NotFoundError()
    if proveedor.disabled_at is not None:
        raise DomainValidationError({"supplier_id": SUPPLIER_DISABLED})


async def list_products(
    db: AsyncSession,
    context: AuthContext,
    *,
    search: str | None = None,
    supplier_id: uuid.UUID | None = None,
    include_disabled: bool = False,
    page: int = 1,
    page_size: int = MAX_PAGE_SIZE,
) -> ProductPage:
    """Una página del catálogo de la empresa de la sesión (CA-4.1 a CA-4.5).

    El término se normaliza igual que el nombre y el SKU almacenados (CA-4.2).
    Buscar con el campo vacío equivale a listar (§5, séptimo caso borde).
    """
    termino = normalize_name(search) if search else None
    return await ProductRepo(db).list(
        context.company_id,
        search=termino or None,
        supplier_id=supplier_id,
        include_disabled=include_disabled,
        page=page,
        page_size=page_size,
    )


async def get_product(
    db: AsyncSession, context: AuthContext, product_id: uuid.UUID
) -> ProductData:
    """NotFoundError si no existe o es de otra empresa: indistinguibles (RN-8)."""
    producto = await ProductRepo(db).get(context.company_id, product_id)
    if producto is None:
        raise NotFoundError()
    return producto


async def create_product(
    db: AsyncSession,
    context: AuthContext,
    *,
    name: str,
    sku: str | None = None,
    supplier_id: uuid.UUID | None = None,
) -> ProductData:
    """Alta de un producto activo (CA-3.1, CA-3.5).

    Los duplicados de nombre y de SKU los detectan los índices únicos parciales,
    también bajo concurrencia (§5): la violación se traduce a error de dominio,
    nunca a un 500.
    """
    normalizado = _validated_name(name)
    codigo, codigo_normalizado = _normalized_sku(sku)
    await _check_supplier(db, context, supplier_id)
    try:
        producto = await ProductRepo(db).create(
            context.company_id,
            name=name,
            name_normalized=normalizado,
            sku=codigo,
            sku_normalized=codigo_normalizado,
            supplier_id=supplier_id,
            created_by=context.user_id,
        )
    except IntegrityError as error:
        await db.rollback()
        raise _duplicate_error(error) from None
    await db.commit()
    return producto


async def update_product(
    db: AsyncSession,
    context: AuthContext,
    product_id: uuid.UUID,
    *,
    name: str,
    sku: str | None = None,
    supplier_id: uuid.UUID | None = None,
) -> ProductData:
    """Edita el producto, con las mismas reglas que el alta (CA-3.7).

    Reasignarlo a un proveedor donde el nombre o el SKU ya están tomados se
    rechaza igual que un alta duplicada (§5, quinto caso borde).
    """
    normalizado = _validated_name(name)
    codigo, codigo_normalizado = _normalized_sku(sku)
    # Comprobar antes de escribir: un id de otra empresa debe fallar como
    # "no encontrado", no como duplicado (RN-8, CA-5.4).
    actual = await get_product(db, context, product_id)
    # Solo se valida el proveedor cuando cambia: RN-4 lo exige "en el momento de
    # asignarlo", y conservar el que ya tenía no es asignarlo. Sin esto, un
    # producto cuyo proveedor se deshabilitó después de crearlo dejaría de poder
    # editarse en cualquier otro campo (D-3, plan §7).
    if supplier_id != (actual.supplier.id if actual.supplier else None):
        await _check_supplier(db, context, supplier_id)
    try:
        await ProductRepo(db).update(
            context.company_id,
            product_id,
            name=name,
            name_normalized=normalizado,
            sku=codigo,
            sku_normalized=codigo_normalizado,
            supplier_id=supplier_id,
        )
    except IntegrityError as error:
        await db.rollback()
        raise _duplicate_error(error) from None
    await db.commit()
    return await get_product(db, context, product_id)


async def disable_product(
    db: AsyncSession, context: AuthContext, product_id: uuid.UUID
) -> None:
    """Deshabilita el producto (CA-3.10, RN-6). Nunca borra.

    Deshabilitar uno ya deshabilitado no es un error: el estado final es el
    pedido.
    """
    await get_product(db, context, product_id)
    await ProductRepo(db).disable(
        context.company_id,
        product_id,
        disabled_by=context.user_id,
        at=datetime.now(UTC),
    )
    await db.commit()


async def enable_product(
    db: AsyncSession, context: AuthContext, product_id: uuid.UUID
) -> None:
    """Rehabilita el producto (CA-3.12).

    CA-3.11 y D-4: si su nombre o su SKU ya los usa un producto activo del mismo
    proveedor, se rechaza igual que un alta duplicada. Lo decide el mismo índice
    único parcial, al dejar de estar la fila fuera de él.
    """
    await get_product(db, context, product_id)
    try:
        await ProductRepo(db).enable(context.company_id, product_id)
    except IntegrityError as error:
        await db.rollback()
        raise _duplicate_error(error) from None
    await db.commit()
