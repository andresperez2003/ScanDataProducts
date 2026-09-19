"""T016: aislamiento entre empresas vía el endpoint sonda (spec HU-4, RN-8, RN-9).

El endpoint /api/v1/_probe y la tabla probe_items son temporales: se eliminan al
cerrar la spec 002, cuando existan recursos de negocio reales.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.models.probe_item import ProbeItem
from src.repos.probe_item import ProbeItemRepo
from tests.integration.conftest import ClientFactory

_CONTRASENA = "Trazabilidad#2026"


@dataclass
class Empresa:
    cliente: AsyncClient
    company_id: uuid.UUID
    user_id: uuid.UUID


async def _empresa(make_client: ClientFactory, nombre: str) -> Empresa:
    cliente = make_client()
    cuerpo = (
        await cliente.post(
            "/api/v1/auth/register",
            json={"company_name": nombre, "username": nombre, "password": _CONTRASENA},
        )
    ).json()
    return Empresa(
        cliente, uuid.UUID(cuerpo["company"]["id"]), uuid.UUID(cuerpo["user"]["id"])
    )


@pytest.fixture
async def a(make_client: ClientFactory) -> Empresa:
    return await _empresa(make_client, "empresa-a")


@pytest.fixture
async def b(make_client: ClientFactory) -> Empresa:
    return await _empresa(make_client, "empresa-b")


async def _item(db: AsyncSession, empresa: Empresa, nombre: str) -> str:
    item = await ProbeItemRepo(db).create(
        empresa.company_id, name=nombre, created_by=empresa.user_id
    )
    return str(item.id)


async def _renombrar(empresa: Empresa, item_id: str, **cuerpo: Any) -> httpx.Response:
    return await empresa.cliente.patch(
        f"/api/v1/_probe/{item_id}",
        json=cuerpo,
        headers={"X-CSRF-Token": empresa.cliente.cookies["csrf_token"]},
    )


# --- CA-4.1 ----------------------------------------------------------------


async def test_ca_4_1_recurso_de_otra_empresa_es_404(
    db_session: AsyncSession, a: Empresa, b: Empresa
) -> None:
    item_a = await _item(db_session, a, "de A")

    ajeno = await b.cliente.get(f"/api/v1/_probe/{item_a}")
    inexistente = await b.cliente.get(f"/api/v1/_probe/{uuid.uuid4()}")

    assert ajeno.status_code == 404
    assert ajeno.json()["error"]["code"] == "NOT_FOUND"
    # RN-9: indistinguible de un recurso que no existe.
    assert ajeno.json() == inexistente.json()


async def test_ca_4_1_recurso_propio_es_visible(
    db_session: AsyncSession, a: Empresa
) -> None:
    item_a = await _item(db_session, a, "de A")

    respuesta = await a.cliente.get(f"/api/v1/_probe/{item_a}")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": item_a, "name": "de A"}


# --- CA-4.2 ----------------------------------------------------------------


async def test_ca_4_2_el_listado_solo_contiene_lo_propio(
    db_session: AsyncSession, a: Empresa, b: Empresa
) -> None:
    propios = {await _item(db_session, a, "a1"), await _item(db_session, a, "a2")}
    await _item(db_session, b, "b1")

    respuesta = await a.cliente.get("/api/v1/_probe")

    assert respuesta.status_code == 200
    assert {x["id"] for x in respuesta.json()["items"]} == propios


async def test_ca_4_2_listado_vacio_aunque_la_otra_empresa_tenga_datos(
    db_session: AsyncSession, a: Empresa, b: Empresa
) -> None:
    await _item(db_session, a, "a1")

    respuesta = await b.cliente.get("/api/v1/_probe")

    assert respuesta.json() == {"items": []}


async def test_principio_4_el_listado_excluye_deshabilitados(
    db_session: AsyncSession, a: Empresa
) -> None:
    activo = await _item(db_session, a, "activo")
    deshabilitado = await db_session.get(
        ProbeItem, uuid.UUID(await _item(db_session, a, "viejo"))
    )
    assert deshabilitado is not None
    deshabilitado.disabled_at = datetime.now(UTC)
    await db_session.flush()

    respuesta = await a.cliente.get("/api/v1/_probe")

    assert [x["id"] for x in respuesta.json()["items"]] == [activo]


async def test_ca_4_3_company_id_en_la_query_se_ignora(
    db_session: AsyncSession, a: Empresa, b: Empresa
) -> None:
    await _item(db_session, b, "b1")

    respuesta = await a.cliente.get(
        "/api/v1/_probe", params={"company_id": str(b.company_id)}
    )

    assert respuesta.json() == {"items": []}


# --- CA-4.4 ----------------------------------------------------------------


async def test_ca_4_4_modificar_recurso_de_otra_empresa_falla_sin_cambiarlo(
    db_session: AsyncSession, a: Empresa, b: Empresa
) -> None:
    item_a = await _item(db_session, a, "original")

    respuesta = await _renombrar(b, item_a, name="pirata")

    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["code"] == "NOT_FOUND"
    sin_cambios = await a.cliente.get(f"/api/v1/_probe/{item_a}")
    assert sin_cambios.json()["name"] == "original"


async def test_ca_4_4_modificar_recurso_propio_funciona(
    db_session: AsyncSession, a: Empresa
) -> None:
    item_a = await _item(db_session, a, "original")

    respuesta = await _renombrar(a, item_a, name="nuevo")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"id": item_a, "name": "nuevo"}


async def test_ca_4_3_company_id_en_el_cuerpo_se_ignora(
    db_session: AsyncSession, a: Empresa, b: Empresa
) -> None:
    item_a = await _item(db_session, a, "original")

    await _renombrar(a, item_a, name="nuevo", company_id=str(b.company_id))

    assert (await b.cliente.get("/api/v1/_probe")).json() == {"items": []}
    assert (await a.cliente.get(f"/api/v1/_probe/{item_a}")).status_code == 200


async def test_modificar_con_nombre_vacio_400(
    db_session: AsyncSession, a: Empresa
) -> None:
    item_a = await _item(db_session, a, "original")

    respuesta = await _renombrar(a, item_a, name="  ")

    assert respuesta.status_code == 400
    assert set(respuesta.json()["error"]["fields"]) == {"name"}


async def test_borde_modificar_sin_csrf_403(
    db_session: AsyncSession, a: Empresa
) -> None:
    item_a = await _item(db_session, a, "original")

    respuesta = await a.cliente.patch(f"/api/v1/_probe/{item_a}", json={"name": "x"})

    assert respuesta.status_code == 403


async def test_ca_3_4_sin_sesion_401(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/_probe")).status_code == 401
