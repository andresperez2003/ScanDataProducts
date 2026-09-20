"""T010: /api/v1/products, los seis endpoints de plan §5.

Un caso por cada código de éxito y cada código de error del contrato. Las reglas
de negocio las cubre `test_products_service.py` (T007); aquí se comprueba la
traducción a HTTP.
"""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.catalog_helpers import Empresa, error_de, registrar
from tests.integration.conftest import ClientFactory

BASE = "/api/v1/products"
SUPPLIERS = "/api/v1/suppliers"


@pytest.fixture
async def a(make_client: ClientFactory) -> Empresa:
    return await registrar(make_client, "empresa-a")


@pytest.fixture
async def b(make_client: ClientFactory) -> Empresa:
    return await registrar(make_client, "empresa-b")


async def _proveedor(empresa: Empresa, nombre: str) -> str:
    respuesta = await empresa.post(SUPPLIERS, name=nombre)
    assert respuesta.status_code == 201, respuesta.text
    identificador: str = respuesta.json()["id"]
    return identificador


async def _alta(empresa: Empresa, nombre: str, **extra: Any) -> str:
    respuesta = await empresa.post(BASE, name=nombre, **extra)
    assert respuesta.status_code == 201, respuesta.text
    identificador: str = respuesta.json()["id"]
    return identificador


# --- POST /products: 201, 400, 404, 409, 403, 401 -------------------------


async def test_ca_3_1_alta_devuelve_201_con_el_producto(a: Empresa) -> None:
    proveedor = await _proveedor(a, "Acme")

    respuesta = await a.post(
        BASE, name="Tornillo 5mm", sku="TOR-5", supplier_id=proveedor
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert (cuerpo["name"], cuerpo["sku"]) == ("Tornillo 5mm", "TOR-5")
    assert cuerpo["supplier"]["id"] == proveedor
    assert cuerpo["supplier"]["name"] == "Acme"


async def test_ca_3_5_alta_sin_proveedor_devuelve_201_con_supplier_nulo(
    a: Empresa,
) -> None:
    respuesta = await a.post(BASE, name="Tornillo")

    assert respuesta.status_code == 201
    assert respuesta.json()["supplier"] is None
    assert respuesta.json()["sku"] is None


async def test_ca_3_4_alta_con_nombre_vacio_devuelve_400(a: Empresa) -> None:
    respuesta = await a.post(BASE, name="  ")

    assert respuesta.status_code == 400
    assert error_de(respuesta) == "VALIDATION_ERROR"
    assert set(respuesta.json()["error"]["fields"]) == {"name"}


async def test_ca_3_6_alta_con_un_proveedor_deshabilitado_devuelve_400(
    a: Empresa,
) -> None:
    proveedor = await _proveedor(a, "Acme")
    await a.accion(f"{SUPPLIERS}/{proveedor}/disable")

    respuesta = await a.post(BASE, name="Tornillo", supplier_id=proveedor)

    # plan §5: error por campo en supplier_id, no un conflicto ni un 500.
    assert respuesta.status_code == 400
    assert error_de(respuesta) == "VALIDATION_ERROR"
    assert set(respuesta.json()["error"]["fields"]) == {"supplier_id"}


async def test_rn_8_alta_con_un_proveedor_de_otra_empresa_devuelve_404(
    a: Empresa, b: Empresa
) -> None:
    ajeno = await _proveedor(b, "Acme de B")

    respuesta = await a.post(BASE, name="Tornillo", supplier_id=ajeno)
    inexistente = await a.post(BASE, name="Tuerca", supplier_id=str(uuid.uuid4()))

    assert respuesta.status_code == 404
    assert error_de(respuesta) == "NOT_FOUND"
    # RN-8: un proveedor ajeno es indistinguible de uno que no existe.
    assert respuesta.json() == inexistente.json()


async def test_ca_3_2_alta_con_nombre_duplicado_devuelve_409(a: Empresa) -> None:
    await _alta(a, "Tornillo")

    respuesta = await a.post(BASE, name="Tornillo")

    assert respuesta.status_code == 409
    assert error_de(respuesta) == "PRODUCT_NAME_TAKEN"


async def test_ca_3_8_alta_con_sku_duplicado_devuelve_409(a: Empresa) -> None:
    await _alta(a, "Tornillo", sku="TOR-5")

    respuesta = await a.post(BASE, name="Tuerca", sku="TOR-5")

    assert respuesta.status_code == 409
    assert error_de(respuesta) == "PRODUCT_SKU_TAKEN"


async def test_ca_3_3_el_mismo_nombre_bajo_otro_proveedor_devuelve_201(
    a: Empresa,
) -> None:
    acme = await _proveedor(a, "Acme")
    await _alta(a, "Tornillo", supplier_id=acme)

    respuesta = await a.post(BASE, name="Tornillo")

    # D-2: sin proveedor es otro grupo de unicidad.
    assert respuesta.status_code == 201


async def test_borde_alta_sin_csrf_devuelve_403(a: Empresa) -> None:
    respuesta = await a.cliente.post(BASE, json={"name": "Tornillo"})

    assert respuesta.status_code == 403
    assert error_de(respuesta) == "CSRF_FAILED"


async def test_alta_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    # Con CSRF válido para llegar a la comprobación de sesión.
    client.cookies.set("csrf_token", "abc")

    respuesta = await client.post(
        BASE, json={"name": "Tornillo"}, headers={"X-CSRF-Token": "abc"}
    )

    assert respuesta.status_code == 401
    assert error_de(respuesta) == "NOT_AUTHENTICATED"


# --- GET /products: 200 y 401 ---------------------------------------------


async def test_ca_4_1_el_listado_devuelve_200_con_la_pagina_y_el_proveedor(
    a: Empresa,
) -> None:
    proveedor = await _proveedor(a, "Acme")
    await _alta(a, "Tornillo", supplier_id=proveedor)
    await _alta(a, "Tuerca")

    respuesta = await a.get(BASE)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["page_size"]) == (2, 1, 20)
    por_nombre = {p["name"]: p["supplier"] for p in cuerpo["items"]}
    assert por_nombre["Tornillo"]["name"] == "Acme"
    # CA-4.1: la ausencia de proveedor es explícita.
    assert por_nombre["Tuerca"] is None


async def test_ca_4_2_la_busqueda_filtra_por_nombre_o_sku(a: Empresa) -> None:
    await _alta(a, "Tornillo hexagonal", sku="TOR-5")
    await _alta(a, "Arandela", sku="ARA-1")

    por_nombre = await a.get(BASE, search="TORNILLO")
    por_sku = await a.get(BASE, search="ara-1")

    assert [p["name"] for p in por_nombre.json()["items"]] == ["Tornillo hexagonal"]
    assert [p["name"] for p in por_sku.json()["items"]] == ["Arandela"]


async def test_ca_4_3_la_busqueda_sin_coincidencias_devuelve_200_y_lista_vacia(
    a: Empresa,
) -> None:
    await _alta(a, "Tornillo")

    respuesta = await a.get(BASE, search="zzz")

    assert respuesta.status_code == 200
    assert (respuesta.json()["items"], respuesta.json()["total"]) == ([], 0)


async def test_ca_4_4_el_listado_solo_trae_activos(a: Empresa) -> None:
    activo = await _alta(a, "Tornillo")
    retirado = await _alta(a, "Tuerca")
    await a.accion(f"{BASE}/{retirado}/disable")

    respuesta = await a.get(BASE)

    assert [p["id"] for p in respuesta.json()["items"]] == [activo]


async def test_ca_4_4_el_historico_se_pide_con_include_disabled(a: Empresa) -> None:
    await _alta(a, "Tornillo")
    retirado = await _alta(a, "Tuerca")
    await a.accion(f"{BASE}/{retirado}/disable")

    respuesta = await a.get(BASE, include_disabled=True)

    assert respuesta.json()["total"] == 2


async def test_ca_4_5_el_filtro_por_proveedor_devuelve_solo_los_suyos(
    a: Empresa,
) -> None:
    acme = await _proveedor(a, "Acme")
    globex = await _proveedor(a, "Globex")
    await _alta(a, "Tornillo", supplier_id=acme)
    await _alta(a, "Tuerca", supplier_id=globex)
    await _alta(a, "Arandela")

    respuesta = await a.get(BASE, supplier_id=acme)

    assert [p["name"] for p in respuesta.json()["items"]] == ["Tornillo"]


async def test_ca_1_6_el_listado_muestra_un_proveedor_deshabilitado(a: Empresa) -> None:
    proveedor = await _proveedor(a, "Acme")
    await _alta(a, "Tornillo", supplier_id=proveedor)
    await a.accion(f"{SUPPLIERS}/{proveedor}/disable")

    respuesta = await a.get(BASE)

    # CA-1.6: el producto lo conserva y lo sigue mostrando.
    item = respuesta.json()["items"][0]
    assert item["supplier"]["name"] == "Acme"
    assert item["supplier"]["disabled_at"] is not None


async def test_d_6_el_tamano_de_pagina_no_puede_superar_el_maximo(a: Empresa) -> None:
    respuesta = await a.get(BASE, page_size=500)

    assert respuesta.status_code == 400
    assert error_de(respuesta) == "VALIDATION_ERROR"


async def test_listar_sin_sesion_devuelve_401(client: AsyncClient) -> None:
    assert (await client.get(BASE)).status_code == 401


# --- GET /products/{id}: 200 y 404 ----------------------------------------


async def test_ca_5_1_leer_el_propio_devuelve_200(a: Empresa) -> None:
    producto = await _alta(a, "Tornillo")

    respuesta = await a.get(f"{BASE}/{producto}")

    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == producto


async def test_ca_5_1_leer_uno_de_otra_empresa_devuelve_404(
    a: Empresa, b: Empresa
) -> None:
    producto = await _alta(a, "Tornillo")

    ajeno = await b.get(f"{BASE}/{producto}")
    inexistente = await b.get(f"{BASE}/{uuid.uuid4()}")

    assert ajeno.status_code == 404
    assert ajeno.json() == inexistente.json()


# --- PATCH /products/{id}: 200, 400, 404, 409 -----------------------------


async def test_ca_3_7_editar_devuelve_200_con_el_producto_actualizado(
    a: Empresa,
) -> None:
    proveedor = await _proveedor(a, "Acme")
    producto = await _alta(a, "Tornillo")

    respuesta = await a.patch(
        f"{BASE}/{producto}", name="Tornillo hexagonal", supplier_id=proveedor
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["name"] == "Tornillo hexagonal"
    assert respuesta.json()["supplier"]["id"] == proveedor


async def test_ca_3_7_quitar_el_proveedor_devuelve_200_con_supplier_nulo(
    a: Empresa,
) -> None:
    proveedor = await _proveedor(a, "Acme")
    producto = await _alta(a, "Tornillo", supplier_id=proveedor)

    respuesta = await a.patch(f"{BASE}/{producto}", name="Tornillo", supplier_id=None)

    assert respuesta.status_code == 200
    assert respuesta.json()["supplier"] is None


async def test_ca_3_4_editar_con_nombre_vacio_devuelve_400(a: Empresa) -> None:
    producto = await _alta(a, "Tornillo")

    respuesta = await a.patch(f"{BASE}/{producto}", name=" ")

    assert respuesta.status_code == 400
    assert set(respuesta.json()["error"]["fields"]) == {"name"}


async def test_ca_3_6_editar_a_un_proveedor_deshabilitado_devuelve_400(
    a: Empresa,
) -> None:
    proveedor = await _proveedor(a, "Acme")
    producto = await _alta(a, "Tornillo")
    await a.accion(f"{SUPPLIERS}/{proveedor}/disable")

    respuesta = await a.patch(
        f"{BASE}/{producto}", name="Tornillo", supplier_id=proveedor
    )

    assert respuesta.status_code == 400
    assert set(respuesta.json()["error"]["fields"]) == {"supplier_id"}


async def test_borde_editar_a_un_nombre_ya_tomado_devuelve_409(a: Empresa) -> None:
    await _alta(a, "Tornillo")
    otro = await _alta(a, "Tuerca")

    respuesta = await a.patch(f"{BASE}/{otro}", name="Tornillo")

    assert respuesta.status_code == 409
    assert error_de(respuesta) == "PRODUCT_NAME_TAKEN"


async def test_ca_3_8_editar_a_un_sku_ya_tomado_devuelve_409(a: Empresa) -> None:
    await _alta(a, "Tornillo", sku="TOR-5")
    otro = await _alta(a, "Tuerca", sku="TUE-1")

    respuesta = await a.patch(f"{BASE}/{otro}", name="Tuerca", sku="TOR-5")

    assert respuesta.status_code == 409
    assert error_de(respuesta) == "PRODUCT_SKU_TAKEN"


async def test_ca_5_4_editar_uno_de_otra_empresa_devuelve_404(
    a: Empresa, b: Empresa
) -> None:
    producto = await _alta(a, "Tornillo")

    respuesta = await b.patch(f"{BASE}/{producto}", name="Pirata")

    assert respuesta.status_code == 404
    assert error_de(respuesta) == "NOT_FOUND"


async def test_borde_editar_sin_csrf_devuelve_403(a: Empresa) -> None:
    producto = await _alta(a, "Tornillo")

    respuesta = await a.cliente.patch(f"{BASE}/{producto}", json={"name": "x"})

    assert respuesta.status_code == 403


# --- POST /products/{id}/disable y /enable: 204, 404, 409 -----------------


async def test_ca_3_10_deshabilitar_devuelve_204(a: Empresa) -> None:
    producto = await _alta(a, "Tornillo")

    respuesta = await a.accion(f"{BASE}/{producto}/disable")

    assert respuesta.status_code == 204
    assert respuesta.content == b""
    assert (await a.get(BASE)).json()["total"] == 0


async def test_ca_3_12_rehabilitar_devuelve_204(a: Empresa) -> None:
    producto = await _alta(a, "Tornillo")
    await a.accion(f"{BASE}/{producto}/disable")

    respuesta = await a.accion(f"{BASE}/{producto}/enable")

    assert respuesta.status_code == 204
    assert (await a.get(BASE)).json()["total"] == 1


async def test_ca_3_11_rehabilitar_con_el_nombre_tomado_devuelve_409(
    a: Empresa,
) -> None:
    viejo = await _alta(a, "Tornillo")
    await a.accion(f"{BASE}/{viejo}/disable")
    await _alta(a, "Tornillo")

    respuesta = await a.accion(f"{BASE}/{viejo}/enable")

    assert respuesta.status_code == 409
    assert error_de(respuesta) == "PRODUCT_NAME_TAKEN"


async def test_ca_3_11_rehabilitar_con_el_sku_tomado_devuelve_409(a: Empresa) -> None:
    viejo = await _alta(a, "Tornillo", sku="TOR-5")
    await a.accion(f"{BASE}/{viejo}/disable")
    await _alta(a, "Tuerca", sku="TOR-5")

    respuesta = await a.accion(f"{BASE}/{viejo}/enable")

    assert respuesta.status_code == 409
    assert error_de(respuesta) == "PRODUCT_SKU_TAKEN"


async def test_ca_5_4_deshabilitar_uno_de_otra_empresa_devuelve_404(
    a: Empresa, b: Empresa
) -> None:
    producto = await _alta(a, "Tornillo")

    respuesta = await b.accion(f"{BASE}/{producto}/disable")

    assert respuesta.status_code == 404
    assert (await a.get(BASE)).json()["total"] == 1


async def test_ca_5_4_rehabilitar_uno_de_otra_empresa_devuelve_404(
    a: Empresa, b: Empresa
) -> None:
    producto = await _alta(a, "Tornillo")
    await a.accion(f"{BASE}/{producto}/disable")

    respuesta = await b.accion(f"{BASE}/{producto}/enable")

    assert respuesta.status_code == 404


async def test_borde_deshabilitar_sin_csrf_devuelve_403(a: Empresa) -> None:
    producto = await _alta(a, "Tornillo")

    respuesta = await a.cliente.post(f"{BASE}/{producto}/disable")

    assert respuesta.status_code == 403
