"""T009: /api/v1/suppliers, los cinco endpoints de plan §5.

Un caso por cada código de éxito y cada código de error del contrato. Las reglas
de negocio las cubre `test_suppliers_service.py` (T006); aquí se comprueba la
traducción a HTTP.
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.catalog_helpers import Empresa, error_de, registrar
from tests.integration.conftest import ClientFactory

BASE = "/api/v1/suppliers"


@pytest.fixture
async def a(make_client: ClientFactory) -> Empresa:
    return await registrar(make_client, "empresa-a")


@pytest.fixture
async def b(make_client: ClientFactory) -> Empresa:
    return await registrar(make_client, "empresa-b")


async def _alta(empresa: Empresa, nombre: str) -> str:
    respuesta = await empresa.post(BASE, name=nombre)
    assert respuesta.status_code == 201, respuesta.text
    identificador: str = respuesta.json()["id"]
    return identificador


# --- POST /suppliers: 201, 400, 409, 403, 401 -----------------------------


async def test_ca_1_1_alta_devuelve_201_con_el_proveedor(a: Empresa) -> None:
    respuesta = await a.post(BASE, name="Acme S.A.")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["name"] == "Acme S.A."
    assert cuerpo["disabled_at"] is None
    assert "company_id" not in cuerpo


async def test_ca_1_3_alta_con_nombre_vacio_devuelve_400(a: Empresa) -> None:
    respuesta = await a.post(BASE, name="   ")

    assert respuesta.status_code == 400
    assert error_de(respuesta) == "VALIDATION_ERROR"
    assert set(respuesta.json()["error"]["fields"]) == {"name"}


async def test_ca_1_3_alta_sin_el_campo_nombre_devuelve_400(a: Empresa) -> None:
    respuesta = await a.post(BASE)

    assert respuesta.status_code == 400
    assert error_de(respuesta) == "VALIDATION_ERROR"


async def test_ca_1_2_alta_duplicada_devuelve_409(a: Empresa) -> None:
    await _alta(a, "Acme")

    respuesta = await a.post(BASE, name="Acme")

    assert respuesta.status_code == 409
    assert error_de(respuesta) == "SUPPLIER_NAME_TAKEN"


async def test_borde_alta_sin_csrf_devuelve_403(a: Empresa) -> None:
    respuesta = await a.cliente.post(BASE, json={"name": "Acme"})

    assert respuesta.status_code == 403
    assert error_de(respuesta) == "CSRF_FAILED"


async def test_alta_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    # Con CSRF válido para llegar a la comprobación de sesión: sin él la
    # petición falla antes con 403, como en `test_auth_api.py` de 001.
    client.cookies.set("csrf_token", "abc")

    respuesta = await client.post(
        BASE, json={"name": "Acme"}, headers={"X-CSRF-Token": "abc"}
    )

    assert respuesta.status_code == 401
    assert error_de(respuesta) == "NOT_AUTHENTICATED"


# --- GET /suppliers: 200 y 401 --------------------------------------------


async def test_ca_2_1_el_listado_devuelve_200_con_la_pagina_y_el_total(
    a: Empresa,
) -> None:
    for i in range(3):
        await _alta(a, f"Proveedor {i}")

    respuesta = await a.get(BASE)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["page_size"]) == (3, 1, 20)
    assert len(cuerpo["items"]) == 3


async def test_ca_2_1_la_segunda_pagina_trae_el_resto(a: Empresa) -> None:
    for i in range(3):
        await _alta(a, f"Proveedor {i}")

    respuesta = await a.get(BASE, page=2, page_size=2)

    cuerpo = respuesta.json()
    assert (len(cuerpo["items"]), cuerpo["total"], cuerpo["page"]) == (1, 3, 2)


async def test_ca_2_2_la_busqueda_filtra_por_nombre(a: Empresa) -> None:
    await _alta(a, "Aceros del Norte")
    await _alta(a, "Globex")

    respuesta = await a.get(BASE, search="ACEROS")

    assert [s["name"] for s in respuesta.json()["items"]] == ["Aceros del Norte"]


async def test_ca_2_3_la_busqueda_sin_coincidencias_devuelve_200_y_lista_vacia(
    a: Empresa,
) -> None:
    await _alta(a, "Acme")

    respuesta = await a.get(BASE, search="zzz")

    # Lista vacía, no un error.
    assert respuesta.status_code == 200
    assert (respuesta.json()["items"], respuesta.json()["total"]) == ([], 0)


async def test_borde_buscar_con_el_campo_vacio_equivale_a_listar(a: Empresa) -> None:
    await _alta(a, "Acme")

    respuesta = await a.get(BASE, search="")

    assert respuesta.json()["total"] == 1


async def test_ca_2_4_el_listado_solo_trae_activos(a: Empresa) -> None:
    activo = await _alta(a, "Acme")
    retirado = await _alta(a, "Globex")
    await a.accion(f"{BASE}/{retirado}/disable")

    respuesta = await a.get(BASE)

    assert [s["id"] for s in respuesta.json()["items"]] == [activo]


async def test_ca_2_4_el_historico_se_pide_con_include_disabled(a: Empresa) -> None:
    await _alta(a, "Acme")
    retirado = await _alta(a, "Globex")
    await a.accion(f"{BASE}/{retirado}/disable")

    respuesta = await a.get(BASE, include_disabled=True)

    cuerpo = respuesta.json()
    assert cuerpo["total"] == 2
    # El estado del deshabilitado es visible (sdd/datos.md).
    deshabilitado = next(s for s in cuerpo["items"] if s["id"] == retirado)
    assert deshabilitado["disabled_at"] is not None


async def test_d_6_el_tamano_de_pagina_no_puede_superar_el_maximo(a: Empresa) -> None:
    respuesta = await a.get(BASE, page_size=500)

    # §7 y D-6: 20 como máximo. La petición se rechaza, no se sirve de más.
    assert respuesta.status_code == 400
    assert error_de(respuesta) == "VALIDATION_ERROR"


async def test_listar_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


# --- PATCH /suppliers/{id}: 200, 400, 409, 404 ----------------------------


async def test_ca_1_4_editar_devuelve_200_con_el_proveedor_actualizado(
    a: Empresa,
) -> None:
    proveedor = await _alta(a, "Acme")

    respuesta = await a.patch(f"{BASE}/{proveedor}", name="Acme S.A.")

    assert respuesta.status_code == 200
    assert respuesta.json()["name"] == "Acme S.A."


async def test_ca_1_3_editar_con_nombre_vacio_devuelve_400(a: Empresa) -> None:
    proveedor = await _alta(a, "Acme")

    respuesta = await a.patch(f"{BASE}/{proveedor}", name=" ")

    assert respuesta.status_code == 400
    assert set(respuesta.json()["error"]["fields"]) == {"name"}


async def test_ca_1_5_editar_al_nombre_de_otro_activo_devuelve_409(a: Empresa) -> None:
    proveedor = await _alta(a, "Acme")
    await _alta(a, "Globex")

    respuesta = await a.patch(f"{BASE}/{proveedor}", name="Globex")

    assert respuesta.status_code == 409
    assert error_de(respuesta) == "SUPPLIER_NAME_TAKEN"
    # El original no cambia.
    sin_cambios = await a.get(f"{BASE}/{proveedor}")
    assert sin_cambios.json()["name"] == "Acme"


async def test_ca_5_4_editar_uno_de_otra_empresa_devuelve_404(
    a: Empresa, b: Empresa
) -> None:
    proveedor = await _alta(a, "Acme")

    respuesta = await b.patch(f"{BASE}/{proveedor}", name="Pirata")

    assert respuesta.status_code == 404
    assert error_de(respuesta) == "NOT_FOUND"


async def test_ca_5_1_editar_uno_inexistente_devuelve_404(a: Empresa) -> None:
    respuesta = await a.patch(f"{BASE}/{uuid.uuid4()}", name="Acme")

    assert respuesta.status_code == 404


async def test_borde_editar_sin_csrf_devuelve_403(a: Empresa) -> None:
    proveedor = await _alta(a, "Acme")

    respuesta = await a.cliente.patch(f"{BASE}/{proveedor}", json={"name": "x"})

    assert respuesta.status_code == 403


# --- GET /suppliers/{id}: 200 y 404 ---------------------------------------


async def test_ca_5_1_leer_el_propio_devuelve_200(a: Empresa) -> None:
    proveedor = await _alta(a, "Acme")

    respuesta = await a.get(f"{BASE}/{proveedor}")

    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == proveedor


async def test_ca_5_1_leer_uno_de_otra_empresa_devuelve_404(
    a: Empresa, b: Empresa
) -> None:
    proveedor = await _alta(a, "Acme")

    ajeno = await b.get(f"{BASE}/{proveedor}")
    inexistente = await b.get(f"{BASE}/{uuid.uuid4()}")

    assert ajeno.status_code == 404
    # RN-8: indistinguible de uno que no existe, en código y en mensaje.
    assert ajeno.json() == inexistente.json()


# --- POST /suppliers/{id}/disable y /enable: 204, 404, 409 ----------------


async def test_ca_1_6_deshabilitar_devuelve_204(a: Empresa) -> None:
    proveedor = await _alta(a, "Acme")

    respuesta = await a.accion(f"{BASE}/{proveedor}/disable")

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert (await a.get(BASE)).json()["total"] == 0


async def test_ca_5_4_deshabilitar_uno_de_otra_empresa_devuelve_404(
    a: Empresa, b: Empresa
) -> None:
    proveedor = await _alta(a, "Acme")

    respuesta = await b.accion(f"{BASE}/{proveedor}/disable")

    assert respuesta.status_code == 404
    # El recurso de A no cambia.
    assert (await a.get(BASE)).json()["total"] == 1


async def test_ca_1_8_rehabilitar_devuelve_204(a: Empresa) -> None:
    proveedor = await _alta(a, "Acme")
    await a.accion(f"{BASE}/{proveedor}/disable")

    respuesta = await a.accion(f"{BASE}/{proveedor}/enable")

    assert respuesta.status_code == 204
    assert (await a.get(BASE)).json()["total"] == 1


async def test_ca_1_7_rehabilitar_con_el_nombre_tomado_devuelve_409(
    a: Empresa,
) -> None:
    viejo = await _alta(a, "Acme")
    await a.accion(f"{BASE}/{viejo}/disable")
    await _alta(a, "Acme")

    respuesta = await a.accion(f"{BASE}/{viejo}/enable")

    assert respuesta.status_code == 409
    assert error_de(respuesta) == "SUPPLIER_NAME_TAKEN"


async def test_ca_5_4_rehabilitar_uno_de_otra_empresa_devuelve_404(
    a: Empresa, b: Empresa
) -> None:
    proveedor = await _alta(a, "Acme")
    await a.accion(f"{BASE}/{proveedor}/disable")

    respuesta = await b.accion(f"{BASE}/{proveedor}/enable")

    assert respuesta.status_code == 404


async def test_borde_deshabilitar_sin_csrf_devuelve_403(a: Empresa) -> None:
    proveedor = await _alta(a, "Acme")

    respuesta = await a.cliente.post(f"{BASE}/{proveedor}/disable")

    assert respuesta.status_code == 403


async def test_deshabilitar_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    client.cookies.set("csrf_token", "abc")

    respuesta = await client.post(
        f"{BASE}/{uuid.uuid4()}/disable", headers={"X-CSRF-Token": "abc"}
    )

    assert respuesta.status_code == 401
    assert error_de(respuesta) == "NOT_AUTHENTICATED"
