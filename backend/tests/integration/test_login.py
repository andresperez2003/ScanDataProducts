"""T011: inicio de sesión (spec HU-2, CA-2.1 a CA-2.4, RN-3, RN-6; plan §5)."""

import statistics
import time
from datetime import UTC, datetime

import pytest
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.errors import DomainError, InvalidCredentialsError
from src.core.security import hash_session_token
from src.models import Session
from src.repos.session import SessionRepo
from src.repos.user import UserRepo
from src.services.auth import AuthResult, login, register

_CONTRASENA = "Trazabilidad#2026"
_AHORA = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


async def _registrar(db: AsyncSession, empresa: str, usuario: str) -> AuthResult:
    return await register(
        db, company_name=empresa, username=usuario, password=_CONTRASENA, now=_AHORA
    )


async def _sesiones_de(db: AsyncSession, resultado: AuthResult) -> int:
    consulta = select(func.count()).where(Session.user_id == resultado.user.id)
    return (await db.exec(consulta)).one()


async def _error_de_login(
    db: AsyncSession, usuario: str, contrasena: str
) -> DomainError:
    with pytest.raises(InvalidCredentialsError) as error:
        await login(db, username=usuario, password=contrasena, now=_AHORA)
    return error.value


async def test_ca_2_1_login_correcto_sin_indicar_empresa(
    db_session: AsyncSession,
) -> None:
    registrado = await _registrar(db_session, "Acme S.A.", "maria")

    resultado = await login(
        db_session, username="maria", password=_CONTRASENA, now=_AHORA
    )

    assert resultado.user.id == registrado.user.id
    assert resultado.company.id == registrado.company.id


async def test_ca_2_1_la_sesion_creada_pertenece_a_la_empresa_del_usuario(
    db_session: AsyncSession,
) -> None:
    # Dos empresas: el usuario de A entra sin mencionar empresa y su sesión es de A.
    empresa_a = await _registrar(db_session, "Empresa A", "usuario_a")
    await _registrar(db_session, "Empresa B", "usuario_b")

    resultado = await login(
        db_session,
        username="usuario_a",
        password=_CONTRASENA,
        now=_AHORA,
    )

    sesion = await SessionRepo(db_session).get_active_by_token_hash(
        hash_session_token(resultado.session_token)
    )
    assert sesion is not None
    assert (sesion.company_id, sesion.user_id) == (
        empresa_a.company.id,
        empresa_a.user.id,
    )
    assert sesion.created_at == _AHORA


async def test_borde_rn_3_login_con_el_usuario_en_otras_mayusculas(
    db_session: AsyncSession,
) -> None:
    registrado = await _registrar(db_session, "Acme", "Maria")

    resultado = await login(
        db_session, username="MARIA", password=_CONTRASENA, now=_AHORA
    )

    assert resultado.user.id == registrado.user.id


async def test_ca_2_2_contrasena_incorrecta_se_rechaza_sin_crear_sesion(
    db_session: AsyncSession,
) -> None:
    registrado = await _registrar(db_session, "Acme", "maria")
    # El registro ya abre una sesión (CA-1.1): se compara antes y después.
    antes = await _sesiones_de(db_session, registrado)

    await _error_de_login(db_session, "maria", "Incorrecta#2026")

    assert await _sesiones_de(db_session, registrado) == antes


async def test_ca_2_3_usuario_inexistente_se_rechaza(db_session: AsyncSession) -> None:
    await _error_de_login(db_session, "nadie", _CONTRASENA)


async def test_ca_2_4_usuario_deshabilitado_se_rechaza_con_credenciales_correctas(
    db_session: AsyncSession,
) -> None:
    registrado = await _registrar(db_session, "Acme", "maria")
    await UserRepo(db_session).disable(
        registrado.company.id,
        registrado.user.id,
        disabled_by=registrado.user.id,
        at=_AHORA,
    )
    antes = await _sesiones_de(db_session, registrado)

    await _error_de_login(db_session, "maria", _CONTRASENA)

    assert await _sesiones_de(db_session, registrado) == antes


async def test_rn_6_mensaje_identico(db_session: AsyncSession) -> None:
    registrado = await _registrar(db_session, "Acme", "maria")
    await _registrar(db_session, "Otra", "pedro")
    await UserRepo(db_session).disable(
        registrado.company.id,
        registrado.user.id,
        disabled_by=registrado.user.id,
        at=_AHORA,
    )

    errores = [
        await _error_de_login(db_session, "pedro", "Incorrecta#2026"),
        await _error_de_login(db_session, "nadie", _CONTRASENA),
        await _error_de_login(db_session, "maria", _CONTRASENA),
    ]

    assert len({(e.code, e.message, type(e)) for e in errores}) == 1


async def _mediana_de_fallos(db: AsyncSession, usuario: str, veces: int) -> float:
    tiempos = []
    for _ in range(veces):
        inicio = time.perf_counter()
        with pytest.raises(InvalidCredentialsError):
            await login(db, username=usuario, password="Incorrecta#2026", now=_AHORA)
        tiempos.append(time.perf_counter() - inicio)
    return statistics.median(tiempos)


async def test_ca_2_3_usuario_inexistente_tarda_lo_mismo_que_uno_existente(
    db_session: AsyncSession,
) -> None:
    await _registrar(db_session, "Acme", "maria")

    existente = await _mediana_de_fallos(db_session, "maria", 20)
    inexistente = await _mediana_de_fallos(db_session, "nadie", 20)

    assert abs(existente - inexistente) < 0.05


async def test_d_4_sin_bloqueo_tras_fallos_repetidos(db_session: AsyncSession) -> None:
    # D-4 (retirada): el bloqueo por intentos fallidos está fuera de alcance.
    registrado = await _registrar(db_session, "Acme", "maria")
    for _ in range(6):
        await _error_de_login(db_session, "maria", "Incorrecta#2026")

    resultado = await login(
        db_session, username="maria", password=_CONTRASENA, now=_AHORA
    )

    assert resultado.user.id == registrado.user.id
