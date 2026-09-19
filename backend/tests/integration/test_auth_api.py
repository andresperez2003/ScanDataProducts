"""T014: API /api/v1/auth/* (plan §5; spec CA-1.1 a CA-1.3, CA-2.x, CA-3.x, CA-4.3, §7)."""

from http.cookies import SimpleCookie
from typing import Any

import httpx
from httpx import AsyncClient

from src.core.config import Settings
from src.core.security import warm_decoy_hash
from src.main import create_app
from tests.integration.conftest import ClientFactory

_CONTRASENA = "Trazabilidad#2026"
_REGISTRO = {"company_name": "Acme S.A.", "username": "maria", "password": _CONTRASENA}


async def _registrar(cliente: AsyncClient, **cambios: str) -> httpx.Response:
    return await cliente.post("/api/v1/auth/register", json={**_REGISTRO, **cambios})


async def _entrar(cliente: AsyncClient, **cuerpo: Any) -> httpx.Response:
    return await cliente.post("/api/v1/auth/login", json=cuerpo)


async def _salir(cliente: AsyncClient, csrf: str | None = "cookie") -> httpx.Response:
    cabeceras = {}
    if csrf == "cookie":
        cabeceras["X-CSRF-Token"] = cliente.cookies["csrf_token"]
    elif csrf is not None:
        cabeceras["X-CSRF-Token"] = csrf
    return await cliente.post("/api/v1/auth/logout", headers=cabeceras)


def _error(respuesta: httpx.Response) -> dict[str, Any]:
    cuerpo: dict[str, Any] = respuesta.json()
    assert set(cuerpo) == {"error"}
    assert set(cuerpo["error"]) == {"code", "message", "fields"}
    return dict(cuerpo["error"])


def _cookies(respuesta: httpx.Response) -> dict[str, str]:
    """Cabecera Set-Cookie completa de cada cookie, en minúsculas."""
    return {
        next(iter(SimpleCookie(linea))): linea.lower()
        for linea in respuesta.headers.get_list("set-cookie")
    }


# --- POST /auth/register ---------------------------------------------------


async def test_ca_1_1_registro_201_con_sesion_iniciada(client: AsyncClient) -> None:
    respuesta = await _registrar(client)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["user"]["username"] == "maria"
    assert cuerpo["company"]["name"] == "Acme S.A."
    assert set(_cookies(respuesta)) == {"session", "csrf_token"}
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json() == cuerpo


async def test_rn_5_la_respuesta_no_contiene_la_contrasena(client: AsyncClient) -> None:
    respuesta = await _registrar(client)

    assert _CONTRASENA not in respuesta.text
    assert "password" not in respuesta.text


async def test_ca_1_3_campo_vacio_400_indica_el_campo(client: AsyncClient) -> None:
    respuesta = await _registrar(client, company_name="")

    assert respuesta.status_code == 400
    error = _error(respuesta)
    assert error["code"] == "VALIDATION_ERROR"
    assert set(error["fields"]) == {"company_name"}


async def test_ca_1_3_campo_ausente_400_indica_el_campo(client: AsyncClient) -> None:
    respuesta = await client.post(
        "/api/v1/auth/register", json={"company_name": "Acme", "password": _CONTRASENA}
    )

    assert respuesta.status_code == 400
    error = _error(respuesta)
    assert error["code"] == "VALIDATION_ERROR"
    assert set(error["fields"]) == {"username"}


async def test_ca_1_4_contrasena_invalida_400(client: AsyncClient) -> None:
    respuesta = await _registrar(client, password="corta")

    assert respuesta.status_code == 400
    assert set(_error(respuesta)["fields"]) == {"password"}


async def test_ca_1_2_empresa_duplicada_409(make_client: ClientFactory) -> None:
    await _registrar(make_client())

    respuesta = await _registrar(make_client(), username="pedro")

    assert respuesta.status_code == 409
    assert _error(respuesta)["code"] == "COMPANY_NAME_TAKEN"


async def test_rn_3_usuario_duplicado_409(make_client: ClientFactory) -> None:
    await _registrar(make_client())

    respuesta = await _registrar(make_client(), company_name="Otra", username="MARIA")

    assert respuesta.status_code == 409
    assert _error(respuesta)["code"] == "USERNAME_TAKEN"


async def test_ca_4_3_company_id_en_el_registro_se_ignora(
    make_client: ClientFactory,
) -> None:
    ajena = (await _registrar(make_client())).json()["company"]["id"]

    respuesta = await _registrar(
        make_client(), company_name="Nueva", username="pedro", company_id=ajena
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["company"]["id"] != ajena


# --- POST /auth/login ------------------------------------------------------


async def test_ca_2_1_login_200_con_cookies(make_client: ClientFactory) -> None:
    registro = (await _registrar(make_client())).json()
    cliente = make_client()

    respuesta = await _entrar(cliente, username="maria", password=_CONTRASENA)

    assert respuesta.status_code == 200
    assert respuesta.json() == registro
    assert set(_cookies(respuesta)) == {"session", "csrf_token"}


async def test_nfr_7_login_solo_usa_usuario_y_contrasena(
    make_client: ClientFactory,
) -> None:
    propia = (await _registrar(make_client())).json()["company"]
    await _registrar(make_client(), company_name="Otra", username="pedro")

    respuesta = await _entrar(
        make_client(), username="maria", password=_CONTRASENA, company_name="Otra"
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["company"] == propia


async def test_ca_2_2_ca_2_3_rn_6_401_identico_con_o_sin_usuario(
    make_client: ClientFactory,
) -> None:
    await _registrar(make_client())
    cliente = make_client()

    mala = await _entrar(cliente, username="maria", password="Incorrecta#2026")
    nadie = await _entrar(cliente, username="nadie", password=_CONTRASENA)

    assert mala.status_code == nadie.status_code == 401
    assert _error(mala)["code"] == "INVALID_CREDENTIALS"
    assert mala.json() == nadie.json()
    assert "set-cookie" not in mala.headers


async def test_ca_2_5_429_con_retry_after(make_client: ClientFactory) -> None:
    await _registrar(make_client())
    cliente = make_client()
    for _ in range(5):
        await _entrar(cliente, username="maria", password="Incorrecta#2026")

    respuesta = await _entrar(cliente, username="maria", password=_CONTRASENA)

    assert respuesta.status_code == 429
    assert _error(respuesta)["code"] == "TOO_MANY_ATTEMPTS"
    assert 0 < int(respuesta.headers["Retry-After"]) <= 15 * 60


async def test_login_sin_contrasena_400(client: AsyncClient) -> None:
    respuesta = await _entrar(client, username="maria")

    assert respuesta.status_code == 400
    assert set(_error(respuesta)["fields"]) == {"password"}


# --- POST /auth/logout -----------------------------------------------------


async def test_ca_3_2_logout_204_y_la_sesion_ya_no_sirve(client: AsyncClient) -> None:
    await _registrar(client)
    cookie_sesion = client.cookies["session"]

    respuesta = await _salir(client)

    assert respuesta.status_code == 204
    # Aunque se reenvíe la cookie anterior, la sesión está revocada.
    client.cookies.set("session", cookie_sesion)
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_borde_logout_sin_cabecera_csrf_403_y_la_sesion_sigue(
    client: AsyncClient,
) -> None:
    await _registrar(client)

    respuesta = await _salir(client, csrf=None)

    assert respuesta.status_code == 403
    assert _error(respuesta)["code"] == "CSRF_FAILED"
    assert (await client.get("/api/v1/auth/me")).status_code == 200


async def test_borde_logout_con_csrf_distinto_403(client: AsyncClient) -> None:
    await _registrar(client)

    respuesta = await _salir(client, csrf="otro-valor")

    assert respuesta.status_code == 403


async def test_ca_3_4_logout_sin_sesion_401(client: AsyncClient) -> None:
    client.cookies.set("csrf_token", "abc")

    respuesta = await _salir(client, csrf="abc")

    assert respuesta.status_code == 401
    assert _error(respuesta)["code"] == "NOT_AUTHENTICATED"


# --- GET /auth/me ----------------------------------------------------------


async def test_ca_3_1_me_200_con_la_sesion(client: AsyncClient) -> None:
    registro = (await _registrar(client)).json()

    respuesta = await client.get("/api/v1/auth/me")

    assert respuesta.status_code == 200
    assert respuesta.json() == registro
    assert set(respuesta.json()["user"]) == {"id", "username"}
    assert set(respuesta.json()["company"]) == {"id", "name"}


async def test_ca_3_4_me_sin_sesion_401(client: AsyncClient) -> None:
    respuesta = await client.get("/api/v1/auth/me")

    assert respuesta.status_code == 401
    assert _error(respuesta)["code"] == "NOT_AUTHENTICATED"


async def test_ca_3_4_me_con_cookie_manipulada_401(client: AsyncClient) -> None:
    await _registrar(client)
    client.cookies.set("session", client.cookies["session"] + "x")

    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_ca_4_3_company_id_en_la_query_se_ignora(
    make_client: ClientFactory,
) -> None:
    ajena = (await _registrar(make_client())).json()["company"]["id"]
    cliente = make_client()
    propia = (await _registrar(cliente, company_name="B", username="b")).json()

    respuesta = await cliente.get("/api/v1/auth/me", params={"company_id": ajena})

    assert respuesta.json()["company"] == propia["company"]


# --- cookies ---------------------------------------------------------------


async def test_nfr_7_flags_de_cookies_en_desarrollo(client: AsyncClient) -> None:
    cookies = _cookies(await _registrar(client))

    assert "httponly" in cookies["session"]
    assert "samesite=lax" in cookies["session"]
    assert "path=/" in cookies["session"]
    assert "httponly" not in cookies["csrf_token"]
    assert "samesite=lax" in cookies["csrf_token"]
    # ENVIRONMENT=development: sin Secure para poder usar http://localhost.
    assert "secure" not in cookies["session"]
    assert "secure" not in cookies["csrf_token"]


async def test_nfr_7_cookies_secure_fuera_de_desarrollo(
    make_client: ClientFactory,
) -> None:
    produccion = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+asyncpg://no-se-usa/x",
        session_secret="s" * 32,
    )
    cliente = make_client(settings=produccion)

    cookies = _cookies(await _registrar(cliente))

    assert "secure" in cookies["session"]
    assert "secure" in cookies["csrf_token"]


# --- arranque --------------------------------------------------------------


async def test_ca_2_3_la_app_genera_el_hash_senuelo_al_arrancar() -> None:
    app = create_app()

    async with app.router.lifespan_context(app):
        # Ya calculado: volver a pedirlo no cuesta otra verificación Argon2.
        await warm_decoy_hash()
