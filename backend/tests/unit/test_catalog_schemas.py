"""T008: contratos de /api/v1/suppliers y /api/v1/products (plan §5)."""

import uuid
from datetime import UTC, datetime

from src.models.schemas.catalog import (
    Page,
    ProductIn,
    ProductOut,
    SupplierIn,
    SupplierOut,
)

_AHORA = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def _supplier_out() -> SupplierOut:
    return SupplierOut(id=uuid.uuid4(), name="Acme S.A.", disabled_at=None)


def test_nfr_consistencia_product_out_lleva_el_proveedor_embebido() -> None:
    salida = ProductOut(
        id=uuid.uuid4(),
        name="Tornillo 5mm",
        sku="TOR-5",
        supplier=_supplier_out(),
        disabled_at=None,
    ).model_dump()

    # §7 "consistencia": el nombre actual del proveedor viaja con el producto.
    assert set(salida["supplier"]) == {"id", "name", "disabled_at"}
    # Nunca un supplier_id suelto que el cliente tenga que resolver por su cuenta.
    assert "supplier_id" not in salida


def test_ca_3_5_un_producto_sin_proveedor_serializa_supplier_nulo() -> None:
    salida = ProductOut(
        id=uuid.uuid4(), name="Tornillo", sku=None, supplier=None, disabled_at=None
    ).model_dump()

    # D-1: la ausencia de proveedor es explícita, no un campo que falta.
    assert salida["supplier"] is None
    assert salida["sku"] is None


def test_ca_2_4_la_salida_muestra_el_estado_de_un_registro_deshabilitado() -> None:
    salida = SupplierOut(id=uuid.uuid4(), name="Acme", disabled_at=_AHORA).model_dump()

    # sdd/datos.md: en el histórico, el estado es visible.
    assert salida["disabled_at"] == _AHORA


def test_ca_5_3_los_schemas_de_entrada_ignoran_un_company_id_del_cliente() -> None:
    proveedor = SupplierIn.model_validate(
        {"name": "Acme", "company_id": str(uuid.uuid4())}
    )
    producto = ProductIn.model_validate(
        {"name": "Tornillo", "company_id": str(uuid.uuid4())}
    )

    # RN-7: la empresa nunca llega del cliente. El campo extra se ignora.
    assert not hasattr(proveedor, "company_id")
    assert not hasattr(producto, "company_id")


def test_ca_3_5_product_in_permite_omitir_sku_y_proveedor() -> None:
    producto = ProductIn.model_validate({"name": "Tornillo"})

    assert (producto.sku, producto.supplier_id) == (None, None)


def test_ca_2_1_la_pagina_lleva_los_elementos_y_el_total() -> None:
    proveedor = _supplier_out()

    pagina = Page[SupplierOut](items=[proveedor], total=25, page=1, page_size=20)

    volcado = pagina.model_dump()
    assert (volcado["total"], volcado["page"], volcado["page_size"]) == (25, 1, 20)
    assert [i["id"] for i in volcado["items"]] == [proveedor.id]


def test_ca_2_3_una_pagina_vacia_es_valida() -> None:
    # CA-2.3 y CA-4.3: buscar sin coincidencias devuelve una lista vacía.
    pagina = Page[ProductOut](items=[], total=0, page=1, page_size=20)

    assert pagina.model_dump()["items"] == []
