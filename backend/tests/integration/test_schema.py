"""T003: restricciones del esquema que resuelven casos de la spec (plan §4).

Consulta el catálogo de Postgres, así que verifica la migración aplicada, no los
modelos en memoria.
"""

from typing import Any

from sqlalchemy import Row, text
from sqlmodel.ext.asyncio.session import AsyncSession


async def _consultar(session: AsyncSession, sql: str, **params: Any) -> list[Row[Any]]:
    """SQL crudo sobre el catálogo, por la conexión de la sesión del test."""
    conexion = await session.connection()
    return list((await conexion.execute(text(sql), params)).all())


async def _columnas_unicas(session: AsyncSession, tabla: str) -> list[set[str]]:
    """Columnas de cada restricción UNIQUE de la tabla."""
    filas = await _consultar(
        session,
        """
            SELECT tc.constraint_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema = tc.table_schema
            WHERE tc.table_schema = 'public'
              AND tc.table_name = :tabla
              AND tc.constraint_type = 'UNIQUE'
        """,
        tabla=tabla,
    )
    por_restriccion: dict[str, set[str]] = {}
    for nombre, columna in filas:
        por_restriccion.setdefault(nombre, set()).add(columna)
    return list(por_restriccion.values())


async def test_rn_2_nombre_de_empresa_normalizado_es_unico(
    db_session: AsyncSession,
) -> None:
    assert {"name_normalized"} in await _columnas_unicas(db_session, "companies")


async def test_rn_3_nombre_de_usuario_es_unico_en_todo_el_sistema(
    db_session: AsyncSession,
) -> None:
    unicas = await _columnas_unicas(db_session, "users")

    # Global (D-1): la restricción es solo sobre el nombre, sin company_id.
    assert {"username_normalized"} in unicas
    assert not any("company_id" in columnas for columnas in unicas)


async def test_ca_3_2_indice_parcial_de_sesiones_no_revocadas(
    db_session: AsyncSession,
) -> None:
    filas = await _consultar(
        db_session, "SELECT indexdef FROM pg_indexes WHERE tablename = 'sessions'"
    )
    definiciones = [fila[0] for fila in filas]

    assert any(
        "(token_hash)" in d and "WHERE (revoked_at IS NULL)" in d for d in definiciones
    )


async def test_ca_1_1_fk_de_empresa_a_usuario_es_diferida(
    db_session: AsyncSession,
) -> None:
    filas = await _consultar(
        db_session,
        """
            SELECT tc.is_deferrable, tc.initially_deferred
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema = tc.table_schema
            WHERE tc.table_schema = 'public'
              AND tc.table_name = 'companies'
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = 'disabled_by'
        """,
    )

    assert [tuple(f) for f in filas] == [("YES", "YES")]


async def test_ca_1_5_sin_columna_de_texto_plano(db_session: AsyncSession) -> None:
    filas = await _consultar(
        db_session,
        """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'users'
        """,
    )
    columnas = {fila[0] for fila in filas}

    assert "password_hash" in columnas
    assert {c for c in columnas if "pass" in c} == {"password_hash"}


async def test_d_4_no_existe_tabla_de_intentos_de_login(
    db_session: AsyncSession,
) -> None:
    # D-4 (retirada): sin bloqueo por intentos no se guarda historial de intentos.
    filas = await _consultar(
        db_session,
        """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'login_attempts'
        """,
    )

    assert filas == []
