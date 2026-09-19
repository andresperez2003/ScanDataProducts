"""T015: logging estructurado (spec CA-1.6, RN-5; constitución, Observabilidad)."""

import json
from typing import Any

import pytest
import structlog
from httpx import AsyncClient

from tests.integration.conftest import ClientFactory

_CONTRASENA = "Trazabilidad#2026"
_REGISTRO = {"company_name": "Acme", "username": "maria", "password": _CONTRASENA}


def _lineas(capturado: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    salida = capturado.readouterr()
    lineas = [json.loads(linea) for linea in salida.out.splitlines() if linea.strip()]
    return lineas


def _peticiones(lineas: list[dict[str, Any]], ruta: str) -> list[dict[str, Any]]:
    return [x for x in lineas if x.get("event") == "request" and x.get("path") == ruta]


async def test_ca_1_6_password_no_aparece_en_logs(
    client: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()

    await client.post("/api/v1/auth/register", json=_REGISTRO)
    await client.post(
        "/api/v1/auth/login", json={"username": "maria", "password": _CONTRASENA}
    )

    salida = capsys.readouterr()
    assert _CONTRASENA not in salida.out + salida.err
    # No pasa en vacío: el registro sí dejó su línea de log.
    lineas = [json.loads(x) for x in salida.out.splitlines() if x.strip()]
    assert _peticiones(lineas, "/api/v1/auth/register")


async def test_ca_1_6_el_filtro_redacta_claves_password_a_cualquier_profundidad(
    client: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()

    structlog.get_logger().info(
        "prueba",
        password="secreto-1",
        datos={"new_password": "secreto-2", "anidado": {"Password": "secreto-3"}},
        lista=[{"password_confirm": "secreto-4"}],
    )

    salida = capsys.readouterr().out
    assert "prueba" in salida
    for secreto in ("secreto-1", "secreto-2", "secreto-3", "secreto-4"):
        assert secreto not in salida


async def test_observabilidad_cada_peticion_lleva_request_id_y_company_id(
    client: AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    empresa = (await client.post("/api/v1/auth/register", json=_REGISTRO)).json()
    await client.get("/api/v1/auth/me")
    await client.get("/api/v1/auth/me")

    lineas = _lineas(capsys)
    registro = _peticiones(lineas, "/api/v1/auth/register")
    me = _peticiones(lineas, "/api/v1/auth/me")

    assert len(registro) == 1
    assert len(me) == 2
    # Sin sesión previa no hay empresa; con sesión, la de la sesión.
    assert registro[0]["company_id"] is None
    assert {x["company_id"] for x in me} == {empresa["company"]["id"]}
    ids = [x["request_id"] for x in registro + me]
    assert all(ids)
    assert len(set(ids)) == 3
    assert {x["status_code"] for x in me} == {200}


async def test_observabilidad_error_manejado_se_registra_una_sola_vez(
    make_client: ClientFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    await make_client().post("/api/v1/auth/register", json=_REGISTRO)
    capsys.readouterr()

    await make_client().post(
        "/api/v1/auth/register", json={**_REGISTRO, "username": "pedro"}
    )

    lineas = _lineas(capsys)
    peticion = _peticiones(lineas, "/api/v1/auth/register")
    assert len(peticion) == 1
    del_request = [
        x for x in lineas if x.get("request_id") == peticion[0]["request_id"]
    ]
    errores = [x for x in del_request if x["event"] == "domain_error"]
    assert len(errores) == 1
    assert errores[0]["code"] == "COMPANY_NAME_TAKEN"
    assert errores[0]["status_code"] == 409
