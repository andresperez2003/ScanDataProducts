"""T004: repositorio de proveedores contra Postgres real (spec HU-2, CA-2.1 a CA-2.4).

Sin mocks: sdd/tests.md exige integración contra la BD real. El `company_id` es el
primer parámetro de todos los métodos (constitución, principio 1), y cada caso de
búsqueda comprueba además que la empresa ajena no se filtra.
"""

import uuid
from datetime import UTC, datetime

from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.normalize import normalize_name
from src.models.domain import SupplierData
from src.repos.supplier import SupplierRepo
from tests.conftest import Tenant


async def _alta(db: AsyncSession, tenant: Tenant, nombre: str) -> SupplierData:
    return await SupplierRepo(db).create(
        tenant.company_id,
        name=nombre,
        name_normalized=normalize_name(nombre),
        created_by=tenant.user_id,
    )


async def _altas(db: AsyncSession, tenant: Tenant, *nombres: str) -> list[SupplierData]:
    return [await _alta(db, tenant, nombre) for nombre in nombres]


# --- CA-2.1: página con el total ------------------------------------------


async def test_ca_2_1_pagina_con_total(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _altas(db_session, a, *(f"Proveedor {i:02d}" for i in range(25)))

    primera, total = await SupplierRepo(db_session).list(
        a.company_id, page=1, page_size=20
    )
    segunda, total_segunda = await SupplierRepo(db_session).list(
        a.company_id, page=2, page_size=20
    )

    # El total son todos los activos, no los de la página (§7, D-6).
    assert (len(primera), total) == (20, 25)
    assert (len(segunda), total_segunda) == (5, 25)
    # Orden estable: ninguna fila se repite entre páginas ni se pierde.
    assert len({s.id for s in primera} | {s.id for s in segunda}) == 25


async def test_ca_2_1_pagina_fuera_de_rango_es_vacia_con_el_total_real(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _altas(db_session, a, "Acme", "Globex")

    items, total = await SupplierRepo(db_session).list(a.company_id, page=9)

    assert (items, total) == ([], 2)


# --- CA-2.2 y CA-2.3: búsqueda --------------------------------------------


async def test_ca_2_2_busqueda_parcial(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _altas(db_session, a, "Aceros del Norte", "Aceros del Sur", "Globex")

    items, total = await SupplierRepo(db_session).list(a.company_id, search="aceros")

    assert {s.name for s in items} == {"Aceros del Norte", "Aceros del Sur"}
    assert total == 2


async def test_ca_2_2_la_busqueda_no_distingue_mayusculas_ni_espacios(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Aceros del Norte")

    # El servicio normaliza el término antes de pasarlo: comparar es una regla
    # de negocio (RN-1), y el repo solo filtra (constitución, principio 3).
    items, _ = await SupplierRepo(db_session).list(
        a.company_id, search=normalize_name("  ACEROS   DEL  ")
    )

    assert [s.name for s in items] == ["Aceros del Norte"]


async def test_ca_2_3_busqueda_sin_coincidencias_devuelve_lista_vacia(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Acme")

    items, total = await SupplierRepo(db_session).list(a.company_id, search="zzz")

    # Lista vacía, no un error (CA-2.3).
    assert (items, total) == ([], 0)


async def test_borde_busqueda_vacia_equivale_a_listar(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _altas(db_session, a, "Acme", "Globex")

    vacia, total_vacia = await SupplierRepo(db_session).list(
        a.company_id, search=normalize_name("   ")
    )
    sin_buscar, total = await SupplierRepo(db_session).list(a.company_id)

    assert [s.id for s in vacia] == [s.id for s in sin_buscar]
    assert total_vacia == total == 2


async def test_borde_los_comodines_del_termino_son_literales(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _altas(db_session, a, "Acme", "Descuento 50%")

    items, _ = await SupplierRepo(db_session).list(a.company_id, search="%")

    # Un '%' escrito por el usuario busca el carácter, no todas las filas.
    assert [s.name for s in items] == ["Descuento 50%"]


# --- CA-2.4: solo activos salvo que se pida el histórico -------------------


async def test_ca_2_4_solo_activos_por_defecto(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    activo, retirado = await _altas(db_session, a, "Acme", "Globex")
    await SupplierRepo(db_session).disable(
        a.company_id, retirado.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    items, total = await SupplierRepo(db_session).list(a.company_id)

    assert [s.id for s in items] == [activo.id]
    assert total == 1


async def test_ca_2_4_el_historico_incluye_los_deshabilitados(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    activo, retirado = await _altas(db_session, a, "Acme", "Globex")
    await SupplierRepo(db_session).disable(
        a.company_id, retirado.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    items, total = await SupplierRepo(db_session).list(
        a.company_id, include_disabled=True
    )

    # sdd/datos.md: el histórico incluye los deshabilitados, con su estado visible.
    assert {s.id for s in items} == {activo.id, retirado.id}
    assert total == 2
    assert next(s for s in items if s.id == retirado.id).disabled_at is not None


# --- Principio 1: el company_id filtra todas las consultas -----------------


async def test_principio_1_listar_con_el_company_id_ajeno_no_devuelve_nada(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    await _altas(db_session, a, "Acme", "Globex")

    items, total = await SupplierRepo(db_session).list(b.company_id)

    assert (items, total) == ([], 0)


async def test_principio_1_buscar_con_el_company_id_ajeno_no_devuelve_nada(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    await _alta(db_session, a, "Acme")

    items, total = await SupplierRepo(db_session).list(b.company_id, search="acme")

    assert (items, total) == ([], 0)


async def test_principio_1_get_con_el_company_id_ajeno_devuelve_none(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    proveedor = await _alta(db_session, a, "Acme")

    assert await SupplierRepo(db_session).get(b.company_id, proveedor.id) is None
    assert await SupplierRepo(db_session).get(a.company_id, proveedor.id) is not None


async def test_principio_1_modificar_con_el_company_id_ajeno_no_cambia_nada(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    proveedor = await _alta(db_session, a, "Acme")
    repo = SupplierRepo(db_session)

    renombrado = await repo.update(
        b.company_id, proveedor.id, name="Pirata", name_normalized="pirata"
    )
    deshabilitado = await repo.disable(
        b.company_id, proveedor.id, disabled_by=b.user_id, at=datetime.now(UTC)
    )

    assert (renombrado, deshabilitado) == (False, False)
    sin_cambios = await repo.get(a.company_id, proveedor.id)
    assert sin_cambios is not None
    assert (sin_cambios.name, sin_cambios.disabled_at) == ("Acme", None)


# --- create, get, update, disable, enable ----------------------------------


async def test_ca_1_1_el_alta_crea_un_proveedor_activo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    proveedor = await _alta(db_session, a, "Acme S.A.")

    assert (proveedor.name, proveedor.disabled_at) == ("Acme S.A.", None)
    assert proveedor.company_id == a.company_id
    assert proveedor.created_at is not None


async def test_ca_1_4_el_cambio_de_nombre_se_guarda(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")

    cambiado = await SupplierRepo(db_session).update(
        a.company_id, proveedor.id, name="Acme S.A.", name_normalized="acme s.a."
    )

    assert cambiado is True
    actualizado = await SupplierRepo(db_session).get(a.company_id, proveedor.id)
    assert actualizado is not None
    assert actualizado.name == "Acme S.A."


async def test_rn_6_deshabilitar_marca_la_fecha_y_no_borra(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")
    repo = SupplierRepo(db_session)

    await repo.disable(
        a.company_id, proveedor.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    # Sigue existiendo y es legible (sdd/datos.md: nada se borra).
    guardado = await repo.get(a.company_id, proveedor.id)
    assert guardado is not None
    assert guardado.disabled_at is not None


async def test_ca_1_8_rehabilitar_deja_el_proveedor_activo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")
    repo = SupplierRepo(db_session)
    await repo.disable(
        a.company_id, proveedor.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    rehabilitado = await repo.enable(a.company_id, proveedor.id)

    assert rehabilitado is True
    activo = await repo.get(a.company_id, proveedor.id)
    assert activo is not None
    assert activo.disabled_at is None


async def test_deshabilitar_dos_veces_no_vuelve_a_aplicar(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")
    repo = SupplierRepo(db_session)
    await repo.disable(
        a.company_id, proveedor.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    segunda = await repo.disable(
        a.company_id, proveedor.id, disabled_by=a.user_id, at=datetime.now(UTC)
    )

    # El servicio distingue "no existe" de "ya estaba"; el repo solo informa
    # de si cambió alguna fila.
    assert segunda is False


async def test_get_de_un_id_inexistente_devuelve_none(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    assert await SupplierRepo(db_session).get(a.company_id, uuid.uuid4()) is None
