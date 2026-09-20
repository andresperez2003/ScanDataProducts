"""Objetos de dominio que devuelven los repositorios (constitución, principio 3).

Inmutables y desacoplados del ORM: quien los recibe no puede disparar consultas
ni modificar filas por accidente.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CompanyData:
    id: uuid.UUID
    name: str
    created_at: datetime
    disabled_at: datetime | None


@dataclass(frozen=True)
class UserData:
    id: uuid.UUID
    company_id: uuid.UUID
    username: str
    password_hash: str
    created_at: datetime
    disabled_at: datetime | None


@dataclass(frozen=True)
class SessionData:
    id: uuid.UUID
    user_id: uuid.UUID
    company_id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class AuthContext:
    """Identidad de la petición autenticada. Único origen del company_id (RN-8)."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    session_id: uuid.UUID


@dataclass(frozen=True)
class SupplierData:
    """Proveedor del catálogo de una empresa (002 HU-1)."""

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    created_at: datetime
    # None = activo. Lo necesita el servicio de productos para RN-4.
    disabled_at: datetime | None


@dataclass(frozen=True)
class ProductData:
    """Producto del catálogo de una empresa (002 HU-3).

    El proveedor viene embebido y leído en la misma consulta, nunca copiado en
    la fila del producto: así el listado siempre muestra su nombre actual (§7,
    "consistencia"). `None` es un producto sin proveedor (D-1).
    """

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    sku: str | None
    supplier: SupplierData | None
    created_at: datetime
    disabled_at: datetime | None
