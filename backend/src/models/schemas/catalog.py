"""Contratos de /api/v1/suppliers y /api/v1/products (plan §5).

Ningún schema de entrada acepta `company_id`: los campos extra se ignoran, así
que indicar otra empresa no tiene efecto (RN-7, CA-5.3). El `company_id` sale
siempre de `get_auth_context`.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class SupplierIn(BaseModel):
    """Alta y edición de proveedor. Solo nombre (D-5)."""

    name: str


class SupplierOut(BaseModel):
    """`disabled_at` nulo = activo. Visible para que el histórico muestre el
    estado y la UI ofrezca rehabilitar (sdd/datos.md)."""

    id: uuid.UUID
    name: str
    disabled_at: datetime | None


class ProductIn(BaseModel):
    """Alta y edición de producto. El proveedor y el SKU son opcionales (D-1).

    `supplier_id` sí llega del cliente —es un dato del producto, no la empresa—,
    y el servicio comprueba que sea de la empresa de la sesión y esté activo
    antes de asignarlo (RN-4, CA-3.6).
    """

    name: str
    sku: str | None = None
    supplier_id: uuid.UUID | None = None


class ProductOut(BaseModel):
    """El proveedor va embebido, nunca como un `supplier_id` suelto.

    Así el listado muestra siempre su nombre actual sin que el cliente tenga que
    resolverlo por su cuenta ni guardar una copia que se desactualice (§7,
    "consistencia"). `None` es un producto sin proveedor.
    """

    id: uuid.UUID
    name: str
    sku: str | None
    supplier: SupplierOut | None
    disabled_at: datetime | None


class Page[T](BaseModel):
    """Envoltorio de los dos listados (CA-2.1, CA-4.1).

    `total` es el número de registros que cumplen el filtro, no el de la página:
    es lo que permite al cliente saber cuántas páginas hay.
    """

    items: list[T]
    total: int
    page: int
    page_size: int
