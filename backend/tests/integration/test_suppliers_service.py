"""T006: reglas del catálogo de proveedores (spec HU-1, CA-1.1 a CA-1.8, RN-1).

Contra Postgres real (sdd/tests.md). Los códigos HTTP de cada caso los cubre
`test_suppliers_api.py` (T009); aquí se prueban las reglas, no la traducción.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.db import get_sessionmaker
from src.core.errors import (
    DomainValidationError,
    DuplicateSupplierNameError,
    NotFoundError,
)
from src.models.company import Company
from src.models.domain import AuthContext, SupplierData
from src.models.supplier import Supplier
from src.models.user import User
from src.services.suppliers import (
    create_supplier,
    disable_supplier,
    enable_supplier,
    get_supplier,
    list_suppliers,
    update_supplier,
)
from tests.conftest import Tenant


def _context(tenant: Tenant) -> AuthContext:
    """El company_id sale siempre de la sesión, nunca del cliente (RN-7)."""
    return AuthContext(
        user_id=tenant.user_id, company_id=tenant.company_id, session_id=uuid.uuid4()
    )


async def _alta(db: AsyncSession, tenant: Tenant, nombre: str) -> SupplierData:
    return await create_supplier(db, _context(tenant), name=nombre)


# --- CA-1.1 a CA-1.3: alta -------------------------------------------------


async def test_ca_1_1_alta_con_nombre_libre_crea_un_proveedor_activo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    proveedor = await _alta(db_session, a, "Acme S.A.")

    assert (proveedor.name, proveedor.disabled_at) == ("Acme S.A.", None)
    assert proveedor.company_id == a.company_id


async def test_ca_1_2_alta_con_nombre_de_un_activo_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Acme")

    with pytest.raises(DuplicateSupplierNameError):
        await _alta(db_session, a, "Acme")


async def test_borde_rn_1_el_nombre_duplicado_se_detecta_sin_mayusculas_ni_espacios(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    await _alta(db_session, a, "Tornillo 5mm")

    # §5, primer caso borde: es el mismo nombre a efectos de unicidad.
    with pytest.raises(DuplicateSupplierNameError):
        await _alta(db_session, a, "  tornillo   5MM ")


async def test_borde_el_nombre_se_guarda_tal_como_lo_escribio_el_usuario(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    proveedor = await _alta(db_session, a, "  Acme   S.A. ")

    # Solo la comparación normaliza; lo almacenado es lo escrito (§5).
    assert proveedor.name == "  Acme   S.A. "


async def test_ca_1_3_alta_con_nombre_vacio_se_rechaza_sin_crear_nada(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    with pytest.raises(DomainValidationError) as error:
        await _alta(db_session, a, "   ")

    assert set(error.value.fields) == {"name"}
    items, total = await list_suppliers(db_session, _context(a))
    assert (items, total) == ([], 0)


async def test_ca_1_2_el_mismo_nombre_es_libre_para_otra_empresa(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    await _alta(db_session, a, "Acme")

    proveedor_b = await _alta(db_session, b, "Acme")

    assert proveedor_b.company_id == b.company_id


# --- CA-1.4 y CA-1.5: edición ---------------------------------------------


async def test_ca_1_4_editar_a_un_nombre_libre_actualiza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")

    actualizado = await update_supplier(
        db_session, _context(a), proveedor.id, name="Acme S.A."
    )

    assert actualizado.name == "Acme S.A."


async def test_ca_1_4_editar_dejando_el_mismo_nombre_no_choca_consigo_mismo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")

    actualizado = await update_supplier(
        db_session, _context(a), proveedor.id, name="ACME"
    )

    assert actualizado.name == "ACME"


async def test_ca_1_5_editar_al_nombre_de_otro_activo_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    uno = await _alta(db_session, a, "Acme")
    await _alta(db_session, a, "Globex")

    with pytest.raises(DuplicateSupplierNameError):
        await update_supplier(db_session, _context(a), uno.id, name="Globex")

    # CA-1.5: el original no cambia.
    sin_cambios = await get_supplier(db_session, _context(a), uno.id)
    assert sin_cambios.name == "Acme"


async def test_ca_1_3_editar_con_nombre_vacio_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")

    with pytest.raises(DomainValidationError) as error:
        await update_supplier(db_session, _context(a), proveedor.id, name=" ")

    assert set(error.value.fields) == {"name"}


async def test_ca_5_4_editar_un_proveedor_de_otra_empresa_es_no_encontrado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    proveedor = await _alta(db_session, a, "Acme")

    with pytest.raises(NotFoundError):
        await update_supplier(db_session, _context(b), proveedor.id, name="Pirata")

    sin_cambios = await get_supplier(db_session, _context(a), proveedor.id)
    assert sin_cambios.name == "Acme"


# --- CA-1.6 a CA-1.8: deshabilitar y rehabilitar --------------------------


async def test_ca_1_6_deshabilitar_lo_saca_de_los_activos(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")

    await disable_supplier(db_session, _context(a), proveedor.id)

    items, total = await list_suppliers(db_session, _context(a))
    assert (items, total) == ([], 0)
    # RN-6: sigue existiendo y es legible.
    guardado = await get_supplier(db_session, _context(a), proveedor.id)
    assert guardado.disabled_at is not None


async def test_rn_1_deshabilitar_libera_el_nombre_para_un_alta_nueva(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")
    await disable_supplier(db_session, _context(a), proveedor.id)

    nuevo = await _alta(db_session, a, "Acme")

    # RN-1: la unicidad es solo entre los activos.
    assert nuevo.id != proveedor.id


async def test_ca_1_7_rehabilitar_con_el_nombre_ya_tomado_se_rechaza(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    viejo = await _alta(db_session, a, "Acme")
    await disable_supplier(db_session, _context(a), viejo.id)
    await _alta(db_session, a, "Acme")

    # D-4: rehabilitar no puede crear una unicidad que un alta nunca permitiría.
    with pytest.raises(DuplicateSupplierNameError):
        await enable_supplier(db_session, _context(a), viejo.id)

    sigue_deshabilitado = await get_supplier(db_session, _context(a), viejo.id)
    assert sigue_deshabilitado.disabled_at is not None


async def test_ca_1_8_rehabilitar_sin_conflicto_lo_deja_activo(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")
    await disable_supplier(db_session, _context(a), proveedor.id)

    await enable_supplier(db_session, _context(a), proveedor.id)

    activo = await get_supplier(db_session, _context(a), proveedor.id)
    assert activo.disabled_at is None
    items, _ = await list_suppliers(db_session, _context(a))
    assert [s.id for s in items] == [proveedor.id]


async def test_deshabilitar_dos_veces_deja_el_mismo_estado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = await _alta(db_session, a, "Acme")
    await disable_supplier(db_session, _context(a), proveedor.id)

    # Sin error: el estado final es el pedido. La spec no define un caso de
    # conflicto para esto.
    await disable_supplier(db_session, _context(a), proveedor.id)

    guardado = await get_supplier(db_session, _context(a), proveedor.id)
    assert guardado.disabled_at is not None


async def test_ca_5_4_deshabilitar_uno_de_otra_empresa_es_no_encontrado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    proveedor = await _alta(db_session, a, "Acme")

    with pytest.raises(NotFoundError):
        await disable_supplier(db_session, _context(b), proveedor.id)

    intacto = await get_supplier(db_session, _context(a), proveedor.id)
    assert intacto.disabled_at is None


async def test_ca_5_1_leer_uno_de_otra_empresa_es_no_encontrado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    proveedor = await _alta(db_session, a, "Acme")

    with pytest.raises(NotFoundError):
        await get_supplier(db_session, _context(b), proveedor.id)


async def test_ca_5_1_un_id_inexistente_es_no_encontrado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies

    with pytest.raises(NotFoundError):
        await get_supplier(db_session, _context(a), uuid.uuid4())


# --- §5: dos altas simultáneas con el mismo nombre -------------------------


@pytest.fixture
async def empresa_confirmada() -> AsyncIterator[Tenant]:
    """Empresa y usuario con COMMIT real, y su limpieza al terminar.

    Las dos altas deben confirmar de verdad para competir por el índice único,
    así que este test no puede usar la transacción revertida de `db_session`
    (mismo motivo que `test_register.py` en 001).
    """
    sufijo = uuid.uuid4().hex[:8]
    async with get_sessionmaker()() as db:
        empresa = Company(
            name=f"Concurrente {sufijo}", name_normalized=f"concurrente {sufijo}"
        )
        db.add(empresa)
        await db.flush()
        usuario = User(
            company_id=empresa.id,
            username=f"usuario-{sufijo}",
            username_normalized=f"usuario-{sufijo}",
            password_hash="hash-de-prueba",
        )
        db.add(usuario)
        await db.commit()
        tenant = Tenant(
            company_id=empresa.id, user_id=usuario.id, username=usuario.username
        )

    yield tenant

    async with get_sessionmaker()() as db:
        await db.exec(delete(Supplier).where(col(Supplier.company_id) == empresa.id))
        await db.exec(delete(User).where(col(User.company_id) == empresa.id))
        await db.exec(delete(Company).where(col(Company.id) == empresa.id))
        await db.commit()


async def test_borde_altas_simultaneas_con_el_mismo_nombre(
    empresa_confirmada: Tenant,
) -> None:
    async def dar_de_alta() -> SupplierData:
        async with get_sessionmaker()() as db:
            return await create_supplier(
                db, _context(empresa_confirmada), name="Acme Concurrente"
            )

    resultados = await asyncio.gather(
        dar_de_alta(), dar_de_alta(), return_exceptions=True
    )

    errores = [r for r in resultados if isinstance(r, BaseException)]
    exitos = [r for r in resultados if not isinstance(r, BaseException)]
    # §5: solo una tiene éxito; la otra recibe el duplicado, nunca un 500.
    assert len(exitos) == 1
    assert len(errores) == 1
    assert isinstance(errores[0], DuplicateSupplierNameError)

    async with get_sessionmaker()() as db:
        guardados = (
            await db.exec(
                select(Supplier).where(
                    col(Supplier.company_id) == empresa_confirmada.company_id
                )
            )
        ).all()
    assert len(guardados) == 1
