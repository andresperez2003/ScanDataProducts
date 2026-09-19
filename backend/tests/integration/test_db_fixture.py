"""T003: infraestructura de base de datos para los tests (sdd/tests.md)."""

from sqlalchemy import text
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.db import get_db
from src.models import Company, User
from tests.conftest import Tenant

# Nombre que solo usan estos dos tests, para no depender de otros datos de la BD.
_NOMBRE_SONDA = "t003 sonda de rollback"


async def _contar_sondas(session: AsyncSession) -> int:
    consulta = select(func.count()).where(Company.name_normalized == _NOMBRE_SONDA)
    return (await session.exec(consulta)).one()


async def test_t003_1_un_test_puede_insertar_una_empresa(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        Company(name="T003 Sonda de rollback", name_normalized=_NOMBRE_SONDA)
    )
    await db_session.commit()

    assert await _contar_sondas(db_session) == 1


async def test_t003_2_la_empresa_del_test_anterior_no_existe(
    db_session: AsyncSession,
) -> None:
    # Se ejecuta después del anterior (orden del archivo): si el rollback no
    # funcionara, la empresa insertada allí seguiría en la tabla.
    assert await _contar_sondas(db_session) == 0


async def test_t003_factoria_crea_dos_empresas_distintas_con_un_usuario_cada_una(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, empresa_b = two_companies

    assert empresa_a.company_id != empresa_b.company_id
    for tenant in two_companies:
        usuarios = await db_session.exec(
            select(User).where(User.company_id == tenant.company_id)
        )
        assert [u.id for u in usuarios.all()] == [tenant.user_id]


async def test_t003_get_db_entrega_una_sesion_conectada() -> None:
    dependencia = get_db()
    session = await anext(dependencia)
    try:
        conexion = await session.connection()
        assert (await conexion.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await dependencia.aclose()
