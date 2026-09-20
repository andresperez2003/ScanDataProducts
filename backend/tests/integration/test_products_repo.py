"""T005: repositorio de productos contra Postgres real (spec HU-4, CA-4.1 a CA-4.5).

Sin mocks (sdd/tests.md). El `company_id` es el primer parámetro de todos los
métodos, y cada caso comprueba además que la empresa ajena no se filtra.
"""

import uuid
from datetime import UTC, datetime

from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.normalize import normalize_name
from src.models.domain import ProductData, SupplierData
from src.models.product import Product
from src.repos.product import ProductRepo
from src.repos.supplier import SupplierRepo
from tests.conftest import Tenant


async def _proveedor(db: AsyncSession, tenant: Tenant, nombre: str) -> SupplierData:
    return await SupplierRepo(db).create(
        tenant.company_id,
        name=nombre,
        name_normalized=normalize_name(nombre),
        created_by=tenant.user_id,
    )


async def _producto(
    db: AsyncSession,
    tenant: Tenant,
    nombre: str,
    *,
    supplier_id: uuid.UUID | None = None,
    sku: str | None = None,
) -> ProductData:
    return await ProductRepo(db).create(
        tenant.company_id,
        name=nombre,
        name_normalized=normalize_name(nombre),
        sku=sku,
        sku_normalized=normalize_name(sku) if sku else None,
        supplier_id=supplier_id,
        created_by=tenant.user_id,
    )


# --- CA-4.1: página con total y proveedor embebido ------------------------


async def test_ca_4_1_pagina_con_proveedor_embebido(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    for i in range(22):
        await _producto(db_session, a, f"Tornillo {i:02d}", supplier_id=acme.id)

    items, total = await ProductRepo(db_session).list(
        a.company_id, page=1, page_size=20
    )

    assert (len(items), total) == (20, 22)
    # §7 "consistencia": el nombre del proveedor se lee, no se copia.
    assert all(p.supplier is not None and p.supplier.name == "Acme" for p in items)


async def test_ca_4_1_un_producto_sin_proveedor_lo_indica_con_none(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _producto(db_session, a, "Tornillo")

    items, _ = await ProductRepo(db_session).list(a.company_id)

    assert [p.supplier for p in items] == [None]


async def test_nfr_consistencia_el_listado_refleja_el_nombre_actual_del_proveedor(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    await _producto(db_session, a, "Tornillo", supplier_id=acme.id)
    await SupplierRepo(db_session).update(
        a.company_id, acme.id, name="Acme S.A.", name_normalized="acme s.a."
    )

    items, _ = await ProductRepo(db_session).list(a.company_id)

    assert items[0].supplier is not None
    assert items[0].supplier.name == "Acme S.A."


async def test_ca_1_6_un_proveedor_deshabilitado_sigue_visible_en_sus_productos(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    await _producto(db_session, a, "Tornillo", supplier_id=acme.id)
    await SupplierRepo(db_session).disable(
        a.company_id, acme.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    items, total = await ProductRepo(db_session).list(a.company_id)

    # CA-1.6, RN-5: el producto sigue activo y conserva su proveedor.
    assert total == 1
    assert items[0].supplier is not None
    assert (items[0].supplier.name, items[0].supplier.disabled_at is None) == (
        "Acme",
        False,
    )


# --- CA-4.2 y CA-4.3: búsqueda por nombre o SKU ---------------------------


async def test_ca_4_2_busqueda_por_nombre_o_sku(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _producto(db_session, a, "Tornillo hexagonal", sku="TOR-5")
    await _producto(db_session, a, "Tuerca", sku="TOR-9")
    await _producto(db_session, a, "Arandela", sku="ARA-1")

    por_nombre, _ = await ProductRepo(db_session).list(a.company_id, search="tornillo")
    por_sku, _ = await ProductRepo(db_session).list(a.company_id, search="tor-")

    assert [p.name for p in por_nombre] == ["Tornillo hexagonal"]
    # CA-4.2: el mismo término busca en el nombre y en el código.
    assert {p.name for p in por_sku} == {"Tornillo hexagonal", "Tuerca"}


async def test_ca_4_2_la_busqueda_no_distingue_mayusculas_ni_espacios(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _producto(db_session, a, "Tornillo hexagonal", sku="TOR-5")

    # El término lo normaliza el servicio (regla de negocio), no el repo.
    items, _ = await ProductRepo(db_session).list(
        a.company_id, search=normalize_name("  TOR-5 ")
    )

    assert [p.name for p in items] == ["Tornillo hexagonal"]


async def test_ca_4_3_busqueda_sin_coincidencias_devuelve_lista_vacia(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _producto(db_session, a, "Tornillo")

    items, total = await ProductRepo(db_session).list(a.company_id, search="zzz")

    assert (items, total) == ([], 0)


async def test_borde_un_producto_sin_sku_no_rompe_la_busqueda(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _producto(db_session, a, "Tornillo")
    await _producto(db_session, a, "Tuerca", sku="TUE-1")

    items, _ = await ProductRepo(db_session).list(a.company_id, search="tornillo")

    # El SKU nulo no descarta la fila al comparar con OR.
    assert [p.name for p in items] == ["Tornillo"]


# --- CA-4.4: solo activos salvo que se pida el histórico ------------------


async def test_ca_4_4_solo_activos_por_defecto(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    activo = await _producto(db_session, a, "Tornillo")
    retirado = await _producto(db_session, a, "Tuerca")
    await ProductRepo(db_session).disable(
        a.company_id, retirado.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    items, total = await ProductRepo(db_session).list(a.company_id)

    assert [p.id for p in items] == [activo.id]
    assert total == 1


async def test_ca_4_4_el_historico_incluye_los_deshabilitados(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    activo = await _producto(db_session, a, "Tornillo")
    retirado = await _producto(db_session, a, "Tuerca")
    await ProductRepo(db_session).disable(
        a.company_id, retirado.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    items, total = await ProductRepo(db_session).list(
        a.company_id, include_disabled=True
    )

    assert {p.id for p in items} == {activo.id, retirado.id}
    assert total == 2


# --- CA-4.5: filtro por proveedor -----------------------------------------


async def test_ca_4_5_filtro_por_proveedor(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    globex = await _proveedor(db_session, a, "Globex")
    await _producto(db_session, a, "Tornillo", supplier_id=acme.id)
    await _producto(db_session, a, "Tuerca", supplier_id=globex.id)
    await _producto(db_session, a, "Arandela")

    items, total = await ProductRepo(db_session).list(a.company_id, supplier_id=acme.id)

    assert [p.name for p in items] == ["Tornillo"]
    assert total == 1


async def test_ca_4_5_el_filtro_por_proveedor_se_combina_con_la_busqueda(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    await _producto(db_session, a, "Tornillo", supplier_id=acme.id)
    await _producto(db_session, a, "Tuerca", supplier_id=acme.id)

    items, _ = await ProductRepo(db_session).list(
        a.company_id, supplier_id=acme.id, search="tuerca"
    )

    assert [p.name for p in items] == ["Tuerca"]


async def test_ca_4_5_filtrar_por_un_proveedor_ajeno_no_devuelve_nada(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    ajeno = await _proveedor(db_session, b, "Acme de B")
    await _producto(db_session, a, "Tornillo")

    items, total = await ProductRepo(db_session).list(
        a.company_id, supplier_id=ajeno.id
    )

    assert (items, total) == ([], 0)


# --- Principio 1: el company_id filtra todas las consultas ----------------


async def test_principio_1_listar_con_el_company_id_ajeno_no_devuelve_nada(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    await _producto(db_session, a, "Tornillo")

    items, total = await ProductRepo(db_session).list(b.company_id)

    assert (items, total) == ([], 0)


async def test_principio_1_get_con_el_company_id_ajeno_devuelve_none(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    producto = await _producto(db_session, a, "Tornillo")

    assert await ProductRepo(db_session).get(b.company_id, producto.id) is None
    assert await ProductRepo(db_session).get(a.company_id, producto.id) is not None


async def test_principio_1_modificar_con_el_company_id_ajeno_no_cambia_nada(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    producto = await _producto(db_session, a, "Tornillo")
    repo = ProductRepo(db_session)

    cambiado = await repo.update(
        b.company_id,
        producto.id,
        name="Pirata",
        name_normalized="pirata",
        sku=None,
        sku_normalized=None,
        supplier_id=None,
    )
    deshabilitado = await repo.disable(
        b.company_id, producto.id, disabled_by=b.user_id, at=datetime.now(UTC)
    )

    assert (cambiado, deshabilitado) == (False, False)
    sin_cambios = await repo.get(a.company_id, producto.id)
    assert sin_cambios is not None
    assert (sin_cambios.name, sin_cambios.disabled_at) == ("Tornillo", None)


# --- create, get, update, disable, enable ---------------------------------


async def test_ca_3_1_el_alta_crea_un_producto_activo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")

    producto = await _producto(
        db_session, a, "Tornillo", supplier_id=acme.id, sku="T-5"
    )

    assert (producto.name, producto.sku, producto.disabled_at) == (
        "Tornillo",
        "T-5",
        None,
    )
    assert producto.supplier is not None
    assert producto.supplier.id == acme.id


async def test_ca_3_5_el_alta_sin_proveedor_deja_supplier_en_none(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    producto = await _producto(db_session, a, "Tornillo")

    assert (producto.supplier, producto.sku) == (None, None)


async def test_ca_3_7_cambiar_el_proveedor_de_un_producto(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _producto(db_session, a, "Tornillo")
    repo = ProductRepo(db_session)

    await repo.update(
        a.company_id,
        producto.id,
        name="Tornillo",
        name_normalized="tornillo",
        sku=None,
        sku_normalized=None,
        supplier_id=acme.id,
    )

    actualizado = await repo.get(a.company_id, producto.id)
    assert actualizado is not None
    assert actualizado.supplier is not None
    assert actualizado.supplier.id == acme.id


async def test_ca_3_7_quitarle_el_proveedor_a_un_producto(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    acme = await _proveedor(db_session, a, "Acme")
    producto = await _producto(db_session, a, "Tornillo", supplier_id=acme.id)
    repo = ProductRepo(db_session)

    await repo.update(
        a.company_id,
        producto.id,
        name="Tornillo",
        name_normalized="tornillo",
        sku=None,
        sku_normalized=None,
        supplier_id=None,
    )

    actualizado = await repo.get(a.company_id, producto.id)
    assert actualizado is not None
    assert actualizado.supplier is None


async def test_rn_6_deshabilitar_marca_la_fecha_y_no_borra(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    producto = await _producto(db_session, a, "Tornillo")
    repo = ProductRepo(db_session)

    await repo.disable(
        a.company_id, producto.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    guardado = await repo.get(a.company_id, producto.id)
    assert guardado is not None
    assert guardado.disabled_at is not None


async def test_ca_3_12_rehabilitar_deja_el_producto_activo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    producto = await _producto(db_session, a, "Tornillo")
    repo = ProductRepo(db_session)
    await repo.disable(
        a.company_id, producto.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    rehabilitado = await repo.enable(a.company_id, producto.id)

    assert rehabilitado is True
    activo = await repo.get(a.company_id, producto.id)
    assert activo is not None
    assert activo.disabled_at is None


async def test_get_de_un_id_inexistente_devuelve_none(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    assert await ProductRepo(db_session).get(a.company_id, uuid.uuid4()) is None


# --- Principio 1: el JOIN a `suppliers` también filtra por empresa ---------


async def test_principio_1_el_join_no_revela_un_proveedor_de_otra_empresa(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    """Defensa en profundidad: el servicio ya impide asignar un proveedor ajeno
    (RN-4), pero la BD no tiene una restricción que lo garantice. Si una fila
    cruzara la frontera, el listado no debe filtrar su nombre igualmente."""
    a, b = two_companies
    ajeno = await _proveedor(db_session, b, "Proveedor de B")
    producto = await _producto(db_session, a, "Tornillo")
    # Se salta el servicio a propósito: simula la fila corrupta.
    fila = await db_session.get(Product, producto.id)
    assert fila is not None
    fila.supplier_id = ajeno.id
    await db_session.flush()

    leido = await ProductRepo(db_session).get(a.company_id, producto.id)
    listados, _ = await ProductRepo(db_session).list(a.company_id)

    # El producto se sigue viendo, pero el nombre de la otra empresa no.
    assert leido is not None
    assert leido.supplier is None
    assert listados[0].supplier is None
