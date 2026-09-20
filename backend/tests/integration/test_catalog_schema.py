"""T001: restricciones de `suppliers` y `products` que viven en la BD (plan §4).

Consulta el catálogo de Postgres y ejercita los índices contra la base real, así
que verifica la migración aplicada, no los modelos en memoria (sdd/datos.md:
"toda restricción que resuelve un caso borde de la spec vive en la base de datos").
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import Row, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.product import Product
from src.models.supplier import Supplier
from tests.conftest import Tenant

# Marcador del grupo "sin proveedor" en supplier_key (plan §4, D-1).
SIN_PROVEEDOR = uuid.UUID("00000000-0000-0000-0000-000000000000")


async def _consultar(session: AsyncSession, sql: str, **params: Any) -> list[Row[Any]]:
    """SQL crudo sobre el catálogo, por la conexión de la sesión del test."""
    conexion = await session.connection()
    return list((await conexion.execute(text(sql), params)).all())


def _sin_parentesis(fragmento: str) -> str:
    """Quita los paréntesis que Postgres añade al reescribir una definición."""
    return " ".join(fragmento.replace("(", " ").replace(")", " ").split())


async def _indice(session: AsyncSession, tabla: str, nombre: str) -> tuple[str, str]:
    """(columnas, condición WHERE) del índice, ambas normalizadas. Único o falla."""
    filas = await _consultar(
        session,
        """
            SELECT indexdef FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = :tabla AND indexname = :nombre
        """,
        tabla=tabla,
        nombre=nombre,
    )
    assert len(filas) == 1, f"no existe el índice {nombre} en {tabla}"
    definicion: str = filas[0][0]
    assert definicion.startswith("CREATE UNIQUE INDEX"), definicion
    cuerpo = definicion.split(" USING btree ", 1)[1]
    columnas, _, condicion = cuerpo.partition(" WHERE ")
    return _sin_parentesis(columnas), _sin_parentesis(condicion)


async def _viola_restriccion(session: AsyncSession, fila: SQLModel) -> bool:
    """True si insertar la fila viola una restricción. Deja la sesión utilizable."""
    try:
        async with session.begin_nested():
            session.add(fila)
            await session.flush()
    except IntegrityError:
        return True
    return False


def _supplier(tenant: Tenant, nombre: str, **extra: Any) -> Supplier:
    return Supplier(
        company_id=tenant.company_id,
        name=nombre,
        name_normalized=nombre.lower(),
        created_by=tenant.user_id,
        **extra,
    )


def _product(tenant: Tenant, nombre: str, **extra: Any) -> Product:
    return Product(
        company_id=tenant.company_id,
        name=nombre,
        name_normalized=nombre.lower(),
        created_by=tenant.user_id,
        **extra,
    )


# --- Los tres índices únicos parciales de plan §4 --------------------------


async def test_rn_1_indice_unico_parcial_de_proveedores_activos(
    db_session: AsyncSession,
) -> None:
    columnas, condicion = await _indice(
        db_session, "suppliers", "ux_suppliers_company_name_active"
    )

    assert columnas == "company_id, name_normalized"
    assert condicion == "disabled_at IS NULL"


async def test_rn_2_indice_unico_parcial_de_nombre_de_producto(
    db_session: AsyncSession,
) -> None:
    columnas, condicion = await _indice(
        db_session, "products", "ux_products_company_supplier_name_active"
    )

    # supplier_key y no supplier_id: dos NULL nunca son iguales en SQL (plan §2, D-1).
    assert columnas == "company_id, supplier_key, name_normalized"
    assert condicion == "disabled_at IS NULL"


async def test_rn_3_indice_unico_parcial_de_sku_no_vacio(
    db_session: AsyncSession,
) -> None:
    columnas, condicion = await _indice(
        db_session, "products", "ux_products_company_supplier_sku_active"
    )

    assert columnas == "company_id, supplier_key, sku_normalized"
    # El SKU vacío queda fuera del índice: dos productos sin SKU no chocan (§5).
    assert condicion == "disabled_at IS NULL AND sku_normalized IS NOT NULL"


async def test_plan_4_supplier_key_es_generada_a_partir_de_supplier_id(
    db_session: AsyncSession,
) -> None:
    filas = await _consultar(
        db_session,
        """
            SELECT is_generated, generation_expression, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'products'
              AND column_name = 'supplier_key'
        """,
    )

    assert len(filas) == 1
    generada, expresion, nula = filas[0]
    assert (generada, nula) == ("ALWAYS", "NO")
    assert "COALESCE" in expresion.upper()
    assert str(SIN_PROVEEDOR) in expresion


# --- RN-1: unicidad del nombre de proveedor --------------------------------


async def test_rn_1_dos_proveedores_activos_con_el_mismo_nombre_chocan(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    db_session.add(_supplier(a, "Acme"))
    await db_session.flush()

    assert await _viola_restriccion(db_session, _supplier(a, "Acme")) is True


async def test_rn_1_el_nombre_se_repite_si_el_primero_esta_deshabilitado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    db_session.add(_supplier(a, "Acme", disabled_at=datetime.now(UTC)))
    await db_session.flush()

    # El índice es parcial: solo los activos compiten por el nombre.
    assert await _viola_restriccion(db_session, _supplier(a, "Acme")) is False


async def test_rn_7_el_mismo_nombre_en_otra_empresa_no_choca(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, b = two_companies
    db_session.add(_supplier(a, "Acme"))
    await db_session.flush()

    assert await _viola_restriccion(db_session, _supplier(b, "Acme")) is False


# --- RN-2: unicidad del nombre de producto, por proveedor ------------------


async def test_rn_2_dos_productos_activos_del_mismo_proveedor_con_igual_nombre_chocan(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = _supplier(a, "Acme")
    db_session.add(proveedor)
    await db_session.flush()
    db_session.add(_product(a, "Tornillo", supplier_id=proveedor.id))
    await db_session.flush()

    choca = await _viola_restriccion(
        db_session, _product(a, "Tornillo", supplier_id=proveedor.id)
    )

    assert choca is True


async def test_ca_3_3_el_mismo_nombre_bajo_otro_proveedor_no_choca(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    uno, otro = _supplier(a, "Acme"), _supplier(a, "Globex")
    db_session.add_all([uno, otro])
    await db_session.flush()
    db_session.add(_product(a, "Tornillo", supplier_id=uno.id))
    await db_session.flush()

    # D-2: la unicidad es por proveedor, no por toda la empresa.
    choca = await _viola_restriccion(
        db_session, _product(a, "Tornillo", supplier_id=otro.id)
    )

    assert choca is False


async def test_ca_3_5_dos_productos_sin_proveedor_con_igual_nombre_chocan(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    db_session.add(_product(a, "Tornillo"))
    await db_session.flush()

    # "Sin proveedor" es su propio grupo de unicidad (D-1), no ausencia de unicidad.
    assert await _viola_restriccion(db_session, _product(a, "Tornillo")) is True


async def test_ca_3_3_sin_proveedor_y_con_proveedor_coexisten_con_igual_nombre(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = _supplier(a, "Acme")
    db_session.add(proveedor)
    await db_session.flush()
    db_session.add(_product(a, "Tornillo"))
    await db_session.flush()

    choca = await _viola_restriccion(
        db_session, _product(a, "Tornillo", supplier_id=proveedor.id)
    )

    assert choca is False


async def test_ca_3_11_el_nombre_se_repite_si_el_primero_esta_deshabilitado(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    db_session.add(_product(a, "Tornillo", disabled_at=datetime.now(UTC)))
    await db_session.flush()

    assert await _viola_restriccion(db_session, _product(a, "Tornillo")) is False


# --- RN-3: unicidad del SKU, por proveedor y solo si no está vacío ---------


async def test_rn_3_dos_productos_del_mismo_proveedor_con_igual_sku_chocan(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    db_session.add(_product(a, "Tornillo", sku="T-5", sku_normalized="t-5"))
    await db_session.flush()

    choca = await _viola_restriccion(
        db_session, _product(a, "Tuerca", sku="T-5", sku_normalized="t-5")
    )

    assert choca is True


async def test_ca_3_9_el_mismo_sku_bajo_otro_proveedor_no_choca(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    proveedor = _supplier(a, "Acme")
    db_session.add(proveedor)
    await db_session.flush()
    db_session.add(_product(a, "Tornillo", sku="T-5", sku_normalized="t-5"))
    await db_session.flush()

    choca = await _viola_restriccion(
        db_session,
        _product(
            a, "Tornillo", supplier_id=proveedor.id, sku="T-5", sku_normalized="t-5"
        ),
    )

    assert choca is False


async def test_borde_dos_productos_sin_sku_no_chocan(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    a, _ = two_companies
    db_session.add(_product(a, "Tornillo"))
    await db_session.flush()

    # §5: la unicidad de SKU solo aplica cuando el campo no está vacío.
    assert await _viola_restriccion(db_session, _product(a, "Tuerca")) is False


# --- Principio 1: company_id obligatorio y con FK en ambas tablas ----------


@pytest.mark.parametrize("tabla", ["suppliers", "products"])
async def test_principio_1_company_id_obligatorio_con_indice_y_fk(
    db_session: AsyncSession, tabla: str
) -> None:
    columna = await _consultar(
        db_session,
        """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :tabla
              AND column_name = 'company_id'
        """,
        tabla=tabla,
    )
    indices = await _consultar(
        db_session,
        "SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=:tabla",
        tabla=tabla,
    )
    fk = await _consultar(
        db_session,
        """
            SELECT ccu.table_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.table_name = :tabla AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = 'company_id'
        """,
        tabla=tabla,
    )

    assert [tuple(f) for f in columna] == [("NO",)]
    assert [tuple(f) for f in fk] == [("companies",)]
    assert any("(company_id)" in fila[0] for fila in indices)
