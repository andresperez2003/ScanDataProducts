"""T012: bloqueo por intentos fallidos (spec CA-2.5, CA-2.6, D-4; plan §4)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.errors import InvalidCredentialsError, TooManyAttemptsError
from src.services.auth import LoginResult, login, register

_CONTRASENA = "Trazabilidad#2026"
_INCORRECTA = "Incorrecta#2026"
_T0 = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
_IP = "203.0.113.10"
_OTRA_IP = "203.0.113.99"


def _min(minutos: float) -> datetime:
    return _T0 + timedelta(minutes=minutos)


async def _entrar(
    db: AsyncSession, usuario: str, contrasena: str, momento: datetime, ip: str = _IP
) -> LoginResult:
    return await login(
        db, username=usuario, password=contrasena, client_ip=ip, now=momento
    )


async def _fallar(
    db: AsyncSession, usuario: str, momento: datetime, ip: str = _IP
) -> None:
    with pytest.raises(InvalidCredentialsError):
        await _entrar(db, usuario, _INCORRECTA, momento, ip)


@pytest.fixture
async def maria(db_session: AsyncSession) -> str:
    await register(
        db_session, company_name="Acme", username="maria", password=_CONTRASENA
    )
    return "maria"


# --- CA-2.5: por usuario ---------------------------------------------------


async def test_ca_2_5_sexto_intento_bloqueado_aunque_sea_correcto(
    db_session: AsyncSession, maria: str
) -> None:
    for minuto in range(5):
        await _fallar(db_session, maria, _min(minuto))

    with pytest.raises(TooManyAttemptsError) as error:
        await _entrar(db_session, maria, _CONTRASENA, _min(5))

    # Bloqueo de 15 minutos desde el 5.º fallo (minuto 4): quedan 14.
    assert error.value.retry_after_seconds == 14 * 60


async def test_ca_2_5_el_bloqueo_dura_15_minutos(
    db_session: AsyncSession, maria: str
) -> None:
    for minuto in range(5):
        await _fallar(db_session, maria, _min(minuto))

    with pytest.raises(TooManyAttemptsError):
        await _entrar(db_session, maria, _CONTRASENA, _min(4 + 14.9))

    resultado = await _entrar(db_session, maria, _CONTRASENA, _min(4 + 15))
    assert resultado.user.username == maria


async def test_ca_2_5_intentos_durante_el_bloqueo_no_lo_alargan(
    db_session: AsyncSession, maria: str
) -> None:
    for minuto in range(5):
        await _fallar(db_session, maria, _min(minuto))
    for minuto in (6, 10, 18):
        with pytest.raises(TooManyAttemptsError):
            await _entrar(db_session, maria, _INCORRECTA, _min(minuto))

    resultado = await _entrar(db_session, maria, _CONTRASENA, _min(19))
    assert resultado.user.username == maria


async def test_ca_2_5_cuatro_fallos_no_bloquean(
    db_session: AsyncSession, maria: str
) -> None:
    for minuto in range(4):
        await _fallar(db_session, maria, _min(minuto))

    resultado = await _entrar(db_session, maria, _CONTRASENA, _min(4))
    assert resultado.user.username == maria


async def test_ca_2_5_un_acceso_correcto_reinicia_la_cuenta(
    db_session: AsyncSession, maria: str
) -> None:
    for minuto in range(4):
        await _fallar(db_session, maria, _min(minuto))
    await _entrar(db_session, maria, _CONTRASENA, _min(4))
    for minuto in range(5, 9):
        await _fallar(db_session, maria, _min(minuto))

    # 8 fallos en 15 min, pero no 5 consecutivos.
    resultado = await _entrar(db_session, maria, _CONTRASENA, _min(9))
    assert resultado.user.username == maria


async def test_ca_2_5_cinco_fallos_repartidos_en_mas_de_15_minutos_no_bloquean(
    db_session: AsyncSession, maria: str
) -> None:
    for minuto in (0, 4, 8, 12, 16):
        await _fallar(db_session, maria, _min(minuto))

    resultado = await _entrar(db_session, maria, _CONTRASENA, _min(17))
    assert resultado.user.username == maria


async def test_ca_2_5_el_bloqueo_de_un_usuario_no_afecta_a_otro(
    db_session: AsyncSession, maria: str
) -> None:
    await register(
        db_session, company_name="Otra", username="pedro", password=_CONTRASENA
    )
    for minuto in range(5):
        await _fallar(db_session, maria, _min(minuto))

    resultado = await _entrar(db_session, "pedro", _CONTRASENA, _min(5))
    assert resultado.user.username == "pedro"


# --- CA-2.6: por origen ----------------------------------------------------


async def _fallos_repartidos(db: AsyncSession, cantidad: int) -> None:
    # Cada usuario falla una sola vez: el límite por usuario nunca se alcanza.
    for i in range(cantidad):
        await _fallar(db, f"inexistente{i}", _min(i * 0.5))


async def test_ca_2_6_veinte_fallos_desde_un_origen_bloquean_ese_origen(
    db_session: AsyncSession, maria: str
) -> None:
    await _fallos_repartidos(db_session, 20)

    with pytest.raises(TooManyAttemptsError) as error:
        await _entrar(db_session, maria, _CONTRASENA, _min(10))

    # Bloqueo de 15 minutos desde el 20.º fallo (minuto 9.5).
    assert error.value.retry_after_seconds == (15 - 0.5) * 60


async def test_ca_2_6_otro_origen_no_queda_bloqueado(
    db_session: AsyncSession, maria: str
) -> None:
    await _fallos_repartidos(db_session, 20)

    resultado = await _entrar(db_session, maria, _CONTRASENA, _min(10), _OTRA_IP)
    assert resultado.user.username == maria


async def test_ca_2_6_diecinueve_fallos_no_bloquean(
    db_session: AsyncSession, maria: str
) -> None:
    await _fallos_repartidos(db_session, 19)

    resultado = await _entrar(db_session, maria, _CONTRASENA, _min(10))
    assert resultado.user.username == maria
