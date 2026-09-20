"""T007: estado de un producto y efecto de deshabilitar su proveedor.

Segunda mitad de las reglas de `test_products_service.py`, separada para no
pasar de 500 líneas (constitución §6). Cubre CA-3.10 a CA-3.12, RN-5 y D-3.
"""

import uuid

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.errors import (
    DomainValidationError,
    DuplicateProductNameError,
    DuplicateProductSkuError,
    NotFoundError,
)
from src.models.domain import AuthContext, ProductData, SupplierData
from src.services.products import (
    create_product,
    disable_product,
    enable_product,
    get_product,
    list_products,
    update_product,
)
from src.services.suppliers import create_supplier, disable_supplier
from tests.conftest import Tenant


def _context(tenant: Tenant) -> AuthContext:
    """El company_id sale siempre de la sesión, nunca del cliente (RN-7)."""
    return AuthContext(
        user_id=tenant.user_id, company_id=tenant.company_id, session_id=uuid.uuid4()
    )


async def _proveedor(db: AsyncSession, tenant: Tenant, nombre: str) -> SupplierData:
    return await create_supplier(db, _context(tenant), name=nombre)


async def _alta(
    db: AsyncSession,
    tenant: Tenant,
    nombre: str,
    *,
    sku: str | None = None,
    supplier_id: uuid.UUID | None = None,
) -> ProductData:
    return await create_product(
        db, _context(tenant), name=nombre, sku=sku, supplier_id=supplier_id
    )


# --- CA-3.10 a CA-3.12: deshabilitar y rehabilitar ------------------------


async def test_ca_3_10_deshabilitar_lo_saca_de_los_activos(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    producto = await _alta(db_session, a, "Tornillo")

    await disable_product(db_session, _context(a), producto.id)

    items, total = await list_products(db_session, _context(a))
    assert (items, total) == ([], 0)
    guardado = await get_product(db_session, _context(a), producto.id)
    assert guardado.disabled_at is not None


async def test_ca_3_11_rehabilitar_con_el_nombre_ya_tomado_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    viejo = await _alta(db_session, a, "Tornillo")
    await disable_product(db_session, _context(a), viejo.id)
    await _alta(db_session, a, "Tornillo")

    with pytest.raises(DuplicateProductNameError):
        await enable_product(db_session, _context(a), viejo.id)

    sigue_deshabilitado = await get_product(db_session, _context(a), viejo.id)
    assert sigue_deshabilitado.disabled_at is not None


async def test_ca_3_11_rehabilitar_con_el_sku_ya_tomado_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    viejo = await _alta(db_session, a, "Tornillo", sku="TOR-5")
    await disable_product(db_session, _context(a), viejo.id)
    await _alta(db_session, a, "Tuerca", sku="TOR-5")

    with pytest.raises(DuplicateProductSkuError):
        await enable_product(db_session, _context(a), viejo.id)


async def test_ca_3_12_rehabilitar_sin_conflicto_lo_deja_activo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    producto = await _alta(db_session, a, "Tornillo")
    await disable_product(db_session, _context(a), producto.id)

    await enable_product(db_session, _context(a), producto.id)

    activo = await get_product(db_session, _context(a), producto.id)
    assert activo.disabled_at is None


async def test_ca_5_4_deshabilitar_uno_de_otra_empresa_es_no_encontrado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    producto = await _alta(db_session, a, "Tornillo")

    with pytest.raises(NotFoundError):
        await disable_product(db_session, _context(b), producto.id)

    intacto = await get_product(db_session, _context(a), producto.id)
    assert intacto.disabled_at is None


# --- RN-5 y D-3: deshabilitar un proveedor no toca sus productos ----------


async def test_rn_5_deshabilitar_proveedor_no_afecta_productos(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _alta(db_session, a, "Tornillo", supplier_id=acme.id)

    await disable_supplier(db_session, _context(a), acme.id)

    # D-3: los productos siguen activos y utilizables.
    guardado = await get_product(db_session, _context(a), producto.id)
    assert guardado.disabled_at is None
    _, total = await list_products(db_session, _context(a))
    assert total == 1


async def test_ca_1_6_proveedor_deshabilitado_se_conserva_en_producto(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _alta(db_session, a, "Tornillo", supplier_id=acme.id)

    await disable_supplier(db_session, _context(a), acme.id)

    # CA-1.6: el producto lo conserva y lo sigue mostrando.
    guardado = await get_product(db_session, _context(a), producto.id)
    assert guardado.supplier is not None
    assert guardado.supplier.name == "Acme"


async def test_d_3_editar_solo_el_nombre_con_el_proveedor_deshabilitado_no_falla(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _alta(db_session, a, "Tornillo", supplier_id=acme.id)
    await disable_supplier(db_session, _context(a), acme.id)

    # plan §7, último riesgo: el producto sigue editable en lo que no es el
    # proveedor, aunque su proveedor ya no sea asignable.
    actualizado = await update_product(
        db_session,
        _context(a),
        producto.id,
        name="Tornillo hexagonal",
        supplier_id=acme.id,
    )

    assert actualizado.name == "Tornillo hexagonal"


async def test_d_3_quitar_un_proveedor_deshabilitado_de_un_producto_no_falla(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _alta(db_session, a, "Tornillo", supplier_id=acme.id)
    await disable_supplier(db_session, _context(a), acme.id)

    actualizado = await update_product(
        db_session, _context(a), producto.id, name="Tornillo", supplier_id=None
    )

    assert actualizado.supplier is None


async def test_rn_5_volver_a_asignar_un_proveedor_deshabilitado_si_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _alta(db_session, a, "Tornillo", supplier_id=acme.id)
    await disable_supplier(db_session, _context(a), acme.id)
    await update_product(
        db_session, _context(a), producto.id, name="Tornillo", supplier_id=None
    )

    # RN-5: "impide que ese proveedor se asigne —de nuevo o por primera vez—".
    # Una vez quitado, volver a ponerlo sí es asignarlo.
    with pytest.raises(DomainValidationError) as error:
        await update_product(
            db_session, _context(a), producto.id, name="Tornillo", supplier_id=acme.id
        )

    assert set(error.value.fields) == {"supplier_id"}
