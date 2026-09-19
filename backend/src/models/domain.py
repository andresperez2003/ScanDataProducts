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
class LoginAttemptData:
    username_normalized: str
    client_ip: str
    succeeded: bool
    attempted_at: datetime


@dataclass(frozen=True)
class AuthContext:
    """Identidad de la petición autenticada. Único origen del company_id (RN-8)."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    session_id: uuid.UUID


@dataclass(frozen=True)
class ProbeItemData:
    """TEMPORAL (T016): se elimina con probe_items al cerrar la spec 002."""

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    disabled_at: datetime | None
