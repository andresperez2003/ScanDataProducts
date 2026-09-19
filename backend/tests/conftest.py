import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest

# Agregar src/ al path para que los imports funcionen
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.db import get_engine
from src.models import Company, User


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Sesión de BD por test, dentro de una transacción que se revierte al final.

    Los `commit()` del código bajo prueba se convierten en savepoints, así que nada
    de lo que escribe un test sobrevive al siguiente (sdd/tests.md, Infraestructura).
    Requiere el esquema aplicado: `alembic upgrade head`.
    """
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@dataclass(frozen=True)
class Tenant:
    """Una empresa de prueba con su único usuario (D-2)."""

    company_id: uuid.UUID
    user_id: uuid.UUID
    username: str


async def _create_tenant(session: AsyncSession, label: str) -> Tenant:
    company = Company(name=f"Empresa {label}", name_normalized=f"empresa {label}")
    session.add(company)
    # La empresa debe existir antes que su usuario (FK users.company_id).
    await session.flush()
    user = User(
        company_id=company.id,
        username=f"usuario_{label}",
        username_normalized=f"usuario_{label}",
        # Marcador: las fixtures no dependen del hash de contraseñas (T004).
        password_hash="hash-de-prueba",
    )
    session.add(user)
    await session.flush()
    return Tenant(company_id=company.id, user_id=user.id, username=user.username)


@pytest.fixture
async def two_companies(db_session: AsyncSession) -> tuple[Tenant, Tenant]:
    """Dos empresas con un usuario cada una, para poder probar el aislamiento."""
    return (
        await _create_tenant(db_session, "a"),
        await _create_tenant(db_session, "b"),
    )
