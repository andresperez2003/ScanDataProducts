"""T013: ciclo de vida de la sesión (spec HU-3, CA-3.1 a CA-3.3, CA-3.5, RN-7, §5)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.errors import NotAuthenticatedError
from src.models.domain import AuthContext
from src.repos.user import UserRepo
from src.services.auth import AuthResult, login, register
from src.services.sessions import end_session, resolve_session

_CONTRASENA = "Trazabilidad#2026"
_T0 = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
_IP = "198.51.100.20"


@pytest.fixture
async def maria(db_session: AsyncSession) -> AuthResult:
    return await register(
        db_session, company_name="Acme", username="maria", password=_CONTRASENA
    )


async def _iniciar(db: AsyncSession, momento: datetime = _T0) -> str:
    resultado = await login(
        db, username="maria", password=_CONTRASENA, client_ip=_IP, now=momento
    )
    return resultado.session_token


async def _rechazada(db: AsyncSession, token: str, momento: datetime) -> None:
    with pytest.raises(NotAuthenticatedError):
        await resolve_session(db, token, now=momento)


async def test_ca_3_1_la_sesion_sigue_valida_en_la_siguiente_peticion(
    db_session: AsyncSession, maria: AuthResult
) -> None:
    token = await _iniciar(db_session)

    contexto = await resolve_session(db_session, token, now=_T0 + timedelta(hours=1))

    assert contexto == AuthContext(
        user_id=maria.user.id,
        company_id=maria.company.id,
        session_id=contexto.session_id,
    )


async def test_ca_3_3_ocho_horas_sin_actividad_cierran_la_sesion(
    db_session: AsyncSession, maria: AuthResult
) -> None:
    token = await _iniciar(db_session)

    await _rechazada(db_session, token, _T0 + timedelta(hours=8))


async def test_ca_3_3_menos_de_ocho_horas_sin_actividad_no_la_cierran(
    db_session: AsyncSession, maria: AuthResult
) -> None:
    token = await _iniciar(db_session)

    await resolve_session(db_session, token, now=_T0 + timedelta(hours=7, minutes=59))


async def test_ca_3_3_la_actividad_renueva_el_plazo_de_inactividad(
    db_session: AsyncSession, maria: AuthResult
) -> None:
    token = await _iniciar(db_session)
    await resolve_session(db_session, token, now=_T0 + timedelta(hours=5))

    # 10 h desde el login, pero solo 5 desde la última actividad.
    await resolve_session(db_session, token, now=_T0 + timedelta(hours=10))


async def test_ca_3_5_quince_dias_cierran_la_sesion_aunque_haya_actividad(
    db_session: AsyncSession, maria: AuthResult
) -> None:
    token = await _iniciar(db_session)
    fin = _T0 + timedelta(days=15)

    momento = _T0
    while momento + timedelta(hours=7) < fin:
        momento += timedelta(hours=7)
        await resolve_session(db_session, token, now=momento)
    await resolve_session(db_session, token, now=fin - timedelta(seconds=1))

    await _rechazada(db_session, token, fin)


async def test_ca_3_2_tras_cerrar_sesion_ya_no_sirve(
    db_session: AsyncSession, maria: AuthResult
) -> None:
    token = await _iniciar(db_session)

    await end_session(db_session, token, now=_T0 + timedelta(minutes=5))

    await _rechazada(db_session, token, _T0 + timedelta(minutes=6))


async def test_borde_reenviar_la_credencial_tras_cerrar_sesion_se_rechaza(
    db_session: AsyncSession, maria: AuthResult
) -> None:
    token = await _iniciar(db_session)
    await end_session(db_session, token, now=_T0 + timedelta(minutes=5))

    with pytest.raises(NotAuthenticatedError):
        await end_session(db_session, token, now=_T0 + timedelta(minutes=6))


async def test_borde_dos_sesiones_del_mismo_usuario_son_independientes(
    db_session: AsyncSession, maria: AuthResult
) -> None:
    portatil = await _iniciar(db_session)
    movil = await _iniciar(db_session, _T0 + timedelta(minutes=1))

    await resolve_session(db_session, portatil, now=_T0 + timedelta(minutes=2))
    await resolve_session(db_session, movil, now=_T0 + timedelta(minutes=2))
    await end_session(db_session, portatil, now=_T0 + timedelta(minutes=3))

    await _rechazada(db_session, portatil, _T0 + timedelta(minutes=4))
    await resolve_session(db_session, movil, now=_T0 + timedelta(minutes=4))


async def test_rn_7_usuario_deshabilitado(
    db_session: AsyncSession, maria: AuthResult
) -> None:
    token = await _iniciar(db_session)
    await resolve_session(db_session, token, now=_T0 + timedelta(minutes=1))

    await UserRepo(db_session).disable(
        maria.company.id,
        maria.user.id,
        disabled_by=maria.user.id,
        at=_T0 + timedelta(minutes=2),
    )

    # Su sesión deja de funcionar en la siguiente petición.
    await _rechazada(db_session, token, _T0 + timedelta(minutes=3))


async def test_ca_3_4_token_desconocido_se_rechaza(db_session: AsyncSession) -> None:
    await _rechazada(db_session, "token-que-nunca-existio", _T0)
