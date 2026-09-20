"""T007: alta y edición del catálogo de productos (CA-3.1 a CA-3.9, RN-2 a RN-4).

Deshabilitar, rehabilitar y el efecto de retirar un proveedor están en
`test_products_state.py`: juntos pasaban de 500 líneas (constitución §6).

Contra Postgres real (sdd/tests.md). Los códigos HTTP de cada caso los cubre
`test_products_api.py` (T010); aquí se prueban las reglas, no la traducción.
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
    SUPPLIER_DISABLED,
    create_product,
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


# --- CA-3.1 a CA-3.5: alta, unicidad por proveedor ------------------------


async def test_ca_3_1_alta_con_nombre_libre_crea_un_producto_activo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")

    producto = await _alta(db_session, a, "Tornillo 5mm", supplier_id=acme.id)

    assert (producto.name, producto.disabled_at) == ("Tornillo 5mm", None)
    assert producto.supplier is not None
    assert producto.supplier.id == acme.id


async def test_ca_3_2_alta_con_nombre_ya_usado_en_ese_proveedor_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    await _alta(db_session, a, "Tornillo", supplier_id=acme.id)

    with pytest.raises(DuplicateProductNameError):
        await _alta(db_session, a, "Tornillo", supplier_id=acme.id)


async def test_borde_rn_2_el_nombre_duplicado_se_detecta_sin_mayusculas_ni_espacios(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Tornillo 5mm")

    with pytest.raises(DuplicateProductNameError):
        await _alta(db_session, a, "  tornillo   5MM ")


async def test_ca_3_3_el_mismo_nombre_bajo_otro_proveedor_se_crea_sin_conflicto(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    globex = await _proveedor(db_session, a, "Globex")
    await _alta(db_session, a, "Tornillo", supplier_id=acme.id)

    # D-2: la unicidad es por proveedor, no por toda la empresa.
    otro = await _alta(db_session, a, "Tornillo", supplier_id=globex.id)

    assert otro.supplier is not None
    assert otro.supplier.id == globex.id


async def test_ca_3_3_sin_proveedor_y_con_proveedor_coexisten_con_el_mismo_nombre(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    sin_proveedor = await _alta(db_session, a, "Tornillo")

    con_proveedor = await _alta(db_session, a, "Tornillo", supplier_id=acme.id)

    assert sin_proveedor.supplier is None
    assert con_proveedor.supplier is not None


async def test_ca_3_4_alta_con_nombre_vacio_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    with pytest.raises(DomainValidationError) as error:
        await _alta(db_session, a, "   ")

    assert set(error.value.fields) == {"name"}
    items, total = await list_products(db_session, _context(a))
    assert (items, total) == ([], 0)


async def test_ca_3_5_alta_sin_proveedor_crea_el_producto_sin_proveedor(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    producto = await _alta(db_session, a, "Tornillo")

    assert producto.supplier is None


async def test_ca_3_5_dos_productos_sin_proveedor_con_el_mismo_nombre_chocan(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Tornillo")

    # D-1: "sin proveedor" es su propio grupo de unicidad.
    with pytest.raises(DuplicateProductNameError):
        await _alta(db_session, a, "Tornillo")


# --- RN-4 y CA-3.6: el proveedor debe ser mío y estar activo --------------


async def test_rn_4_proveedor_debe_estar_activo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    await disable_supplier(db_session, _context(a), acme.id)

    with pytest.raises(DomainValidationError) as error:
        await _alta(db_session, a, "Tornillo", supplier_id=acme.id)

    # CA-3.6: error por campo, no un 500 ni un conflicto.
    assert error.value.fields == {"supplier_id": SUPPLIER_DISABLED}


async def test_ca_3_6_asignar_un_proveedor_deshabilitado_al_editar_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _alta(db_session, a, "Tornillo")
    await disable_supplier(db_session, _context(a), acme.id)

    with pytest.raises(DomainValidationError) as error:
        await update_product(
            db_session, _context(a), producto.id, name="Tornillo", supplier_id=acme.id
        )

    assert set(error.value.fields) == {"supplier_id"}


async def test_rn_8_un_proveedor_de_otra_empresa_es_no_encontrado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    ajeno = await _proveedor(db_session, b, "Acme de B")

    with pytest.raises(NotFoundError):
        await _alta(db_session, a, "Tornillo", supplier_id=ajeno.id)


async def test_rn_8_un_proveedor_ajeno_deshabilitado_no_se_distingue_de_inexistente(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    ajeno = await _proveedor(db_session, b, "Acme de B")
    await disable_supplier(db_session, _context(b), ajeno.id)

    # Decir "está deshabilitado" revelaría que existe en otra empresa (RN-8).
    with pytest.raises(NotFoundError):
        await _alta(db_session, a, "Tornillo", supplier_id=ajeno.id)
    with pytest.raises(NotFoundError):
        await _alta(db_session, a, "Tuerca", supplier_id=uuid.uuid4())


# --- CA-3.7: edición -------------------------------------------------------


async def test_ca_3_7_cambiar_el_proveedor_actualiza_el_producto(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _alta(db_session, a, "Tornillo")

    actualizado = await update_product(
        db_session, _context(a), producto.id, name="Tornillo", supplier_id=acme.id
    )

    assert actualizado.supplier is not None
    assert actualizado.supplier.id == acme.id


async def test_ca_3_7_quitarle_el_proveedor_es_un_cambio_valido(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _alta(db_session, a, "Tornillo", supplier_id=acme.id)

    actualizado = await update_product(
        db_session, _context(a), producto.id, name="Tornillo", supplier_id=None
    )

    assert actualizado.supplier is None


async def test_borde_reasignar_a_un_proveedor_donde_el_nombre_ya_existe_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    await _alta(db_session, a, "Tornillo", supplier_id=acme.id)
    suelto = await _alta(db_session, a, "Tornillo")

    # §5, quinto caso borde: se rechaza igual que un alta duplicada.
    with pytest.raises(DuplicateProductNameError):
        await update_product(
            db_session, _context(a), suelto.id, name="Tornillo", supplier_id=acme.id
        )


async def test_ca_3_4_editar_con_nombre_vacio_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    producto = await _alta(db_session, a, "Tornillo")

    with pytest.raises(DomainValidationError) as error:
        await update_product(db_session, _context(a), producto.id, name="  ")

    assert set(error.value.fields) == {"name"}


async def test_ca_5_4_editar_un_producto_de_otra_empresa_es_no_encontrado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    producto = await _alta(db_session, a, "Tornillo")

    with pytest.raises(NotFoundError):
        await update_product(db_session, _context(b), producto.id, name="Pirata")

    sin_cambios = await get_product(db_session, _context(a), producto.id)
    assert sin_cambios.name == "Tornillo"


# --- CA-3.8 y CA-3.9: unicidad del SKU ------------------------------------


async def test_ca_3_8_alta_con_sku_ya_usado_en_ese_proveedor_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Tornillo", sku="TOR-5")

    with pytest.raises(DuplicateProductSkuError):
        await _alta(db_session, a, "Tuerca", sku="TOR-5")


async def test_borde_rn_3_el_sku_duplicado_se_detecta_sin_mayusculas_ni_espacios(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Tornillo", sku="TOR-5")

    # §5, segundo caso borde.
    with pytest.raises(DuplicateProductSkuError):
        await _alta(db_session, a, "Tuerca", sku="  tor-5 ")


async def test_ca_3_9_el_mismo_sku_bajo_otro_proveedor_se_crea_sin_conflicto(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    await _alta(db_session, a, "Tornillo", sku="TOR-5")

    otro = await _alta(db_session, a, "Tornillo", sku="TOR-5", supplier_id=acme.id)

    assert otro.sku == "TOR-5"


async def test_borde_dos_productos_del_mismo_proveedor_sin_sku_no_chocan(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Tornillo")

    # §5, último caso borde: la unicidad de SKU solo aplica si no está vacío.
    otro = await _alta(db_session, a, "Tuerca")

    assert otro.sku is None


async def test_borde_un_sku_en_blanco_equivale_a_no_tener_sku(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Tornillo", sku="   ")

    otro = await _alta(db_session, a, "Tuerca", sku="")

    assert otro.sku is None


async def test_ca_3_8_editar_a_un_sku_ya_usado_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Tornillo", sku="TOR-5")
    otro = await _alta(db_session, a, "Tuerca", sku="TUE-1")

    with pytest.raises(DuplicateProductSkuError):
        await update_product(
            db_session, _context(a), otro.id, name="Tuerca", sku="TOR-5"
        )
