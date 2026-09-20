"""T011: aislamiento entre empresas del catálogo (spec HU-5, CA-5.1 a CA-5.4).

sdd/tests.md: "un test de aislamiento por cada endpoint que lea o escriba datos
de negocio. Este test no es opcional en ningún endpoint". Cada caso se ejecuta
contra `suppliers` y contra `products`, que comparten forma de contrato.
"""

import uuid

import pytest

from tests.integration.catalog_helpers import Empresa, error_de, registrar
from tests.integration.conftest import ClientFactory

# Los dos recursos de negocio de esta spec. Ambos aceptan `name` en el alta.
RECURSOS = ["suppliers", "products"]


@pytest.fixture
async def a(make_client: ClientFactory) -> Empresa:
    return await registrar(make_client, "empresa-a")


@pytest.fixture
async def b(make_client: ClientFactory) -> Empresa:
    return await registrar(make_client, "empresa-b")


async def _alta(empresa: Empresa, recurso: str, nombre: str) -> str:
    respuesta = await empresa.post(f"/api/v1/{recurso}", name=nombre)
    assert respuesta.status_code == 201, respuesta.text
    identificador: str = respuesta.json()["id"]
    return identificador


# --- CA-5.1: un recurso ajeno es indistinguible de uno inexistente --------


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_1_no_encontrado_de_otra_empresa(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    de_a = await _alta(a, recurso, "De la empresa A")

    ajeno = await b.get(f"/api/v1/{recurso}/{de_a}")
    inexistente = await b.get(f"/api/v1/{recurso}/{uuid.uuid4()}")

    assert ajeno.status_code == 404
    assert error_de(ajeno) == "NOT_FOUND"
    # RN-8: mismo código y mismo mensaje. Nada revela que exista en otra empresa.
    assert ajeno.json() == inexistente.json()


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_1_el_propio_si_se_lee(a: Empresa, recurso: str) -> None:
    de_a = await _alta(a, recurso, "De la empresa A")

    respuesta = await a.get(f"/api/v1/{recurso}/{de_a}")

    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == de_a


# --- CA-5.2: los listados solo contienen lo propio ------------------------


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_2_listado_solo_propio(a: Empresa, b: Empresa, recurso: str) -> None:
    propios = {
        await _alta(a, recurso, "Uno de A"),
        await _alta(a, recurso, "Otro de A"),
    }
    await _alta(b, recurso, "Uno de B")

    respuesta = await a.get(f"/api/v1/{recurso}")

    assert {x["id"] for x in respuesta.json()["items"]} == propios
    assert respuesta.json()["total"] == 2


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_2_el_listado_esta_vacio_aunque_la_otra_empresa_tenga_datos(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    await _alta(a, recurso, "Uno de A")

    respuesta = await b.get(f"/api/v1/{recurso}")

    assert (respuesta.json()["items"], respuesta.json()["total"]) == ([], 0)


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_2_la_busqueda_no_alcanza_a_la_otra_empresa(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    await _alta(a, recurso, "Tornillo secreto")

    respuesta = await b.get(f"/api/v1/{recurso}", search="tornillo")

    assert respuesta.json()["items"] == []


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_2_el_historico_tampoco_cruza_empresas(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    de_a = await _alta(a, recurso, "Uno de A")
    await a.accion(f"/api/v1/{recurso}/{de_a}/disable")

    respuesta = await b.get(f"/api/v1/{recurso}", include_disabled=True)

    # Ni siquiera pidiendo el histórico aparece lo de otra empresa.
    assert respuesta.json()["total"] == 0


# --- CA-5.3: un company_id enviado por el cliente se ignora ---------------


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_3_company_id_del_cuerpo_se_ignora(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    respuesta = await a.post(
        f"/api/v1/{recurso}", name="Intruso", company_id=str(b.company_id)
    )

    assert respuesta.status_code == 201
    # RN-7: se creó en A, la empresa de la sesión, no en la que pidió el cliente.
    assert (await b.get(f"/api/v1/{recurso}")).json()["total"] == 0
    assert (await a.get(f"/api/v1/{recurso}")).json()["total"] == 1


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_3_company_id_en_la_query_se_ignora(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    await _alta(b, recurso, "Uno de B")

    respuesta = await a.get(f"/api/v1/{recurso}", company_id=str(b.company_id))

    assert respuesta.json()["items"] == []


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_3_company_id_en_la_cabecera_se_ignora(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    await _alta(b, recurso, "Uno de B")

    respuesta = await a.cliente.get(
        f"/api/v1/{recurso}", headers={"X-Company-Id": str(b.company_id)}
    )

    assert respuesta.json()["items"] == []


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_3_company_id_al_editar_se_ignora(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    de_a = await _alta(a, recurso, "Uno de A")

    await a.patch(
        f"/api/v1/{recurso}/{de_a}", name="Renombrado", company_id=str(b.company_id)
    )

    assert (await b.get(f"/api/v1/{recurso}")).json()["total"] == 0
    assert (await a.get(f"/api/v1/{recurso}/{de_a}")).json()["name"] == "Renombrado"


# --- CA-5.4: modificar un recurso ajeno falla y no lo cambia --------------


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_4_modificar_ajeno_falla(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    de_a = await _alta(a, recurso, "Original")

    editar = await b.patch(f"/api/v1/{recurso}/{de_a}", name="Pirata")
    deshabilitar = await b.accion(f"/api/v1/{recurso}/{de_a}/disable")

    assert (editar.status_code, deshabilitar.status_code) == (404, 404)
    assert (error_de(editar), error_de(deshabilitar)) == ("NOT_FOUND", "NOT_FOUND")
    # El recurso de A no cambió por ninguna de las dos vías.
    propio = (await a.get(f"/api/v1/{recurso}/{de_a}")).json()
    assert (propio["name"], propio["disabled_at"]) == ("Original", None)


@pytest.mark.parametrize("recurso", RECURSOS)
async def test_ca_5_4_rehabilitar_ajeno_falla(
    a: Empresa, b: Empresa, recurso: str
) -> None:
    de_a = await _alta(a, recurso, "Original")
    await a.accion(f"/api/v1/{recurso}/{de_a}/disable")

    respuesta = await b.accion(f"/api/v1/{recurso}/{de_a}/enable")

    assert respuesta.status_code == 404
    # Sigue deshabilitado: la empresa B no pudo tocarlo.
    propio = (await a.get(f"/api/v1/{recurso}/{de_a}")).json()
    assert propio["disabled_at"] is not None


# --- RN-4 y RN-8: el supplier_id ajeno tampoco cruza la frontera ----------


async def test_ca_5_4_no_se_puede_asignar_un_proveedor_de_otra_empresa(
    a: Empresa, b: Empresa
) -> None:
    ajeno = await _alta(b, "suppliers", "Proveedor de B")

    alta = await a.post("/api/v1/products", name="Tornillo", supplier_id=ajeno)
    propio = await _alta(a, "products", "Tuerca")
    edicion = await a.patch(
        f"/api/v1/products/{propio}", name="Tuerca", supplier_id=ajeno
    )

    # RN-8: el proveedor ajeno es "no encontrado", ni en el alta ni en la edición.
    assert (alta.status_code, edicion.status_code) == (404, 404)
    assert (await a.get(f"/api/v1/products/{propio}")).json()["supplier"] is None


async def test_ca_5_2_el_filtro_por_un_proveedor_ajeno_no_devuelve_nada(
    a: Empresa, b: Empresa
) -> None:
    ajeno = await _alta(b, "suppliers", "Proveedor de B")
    await _alta(b, "products", "Producto de B")
    await _alta(a, "products", "Producto de A")

    respuesta = await a.get("/api/v1/products", supplier_id=ajeno)

    # Ni un filtro con un id ajeno abre una ventana a la otra empresa.
    assert respuesta.json()["items"] == []
