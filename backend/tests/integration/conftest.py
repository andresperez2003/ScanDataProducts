from collections.abc import AsyncIterator, Callable

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings, get_settings
from src.core.db import get_db
from src.main import create_app

ClientFactory = Callable[..., AsyncClient]


@pytest.fixture
async def make_client(db_session: AsyncSession) -> AsyncIterator[ClientFactory]:
    """Clientes HTTP contra la app real, con la BD del test (transacción revertida).

    Cada cliente tiene su propio tarro de cookies: equivale a un navegador distinto.
    `settings` permite simular otro entorno (p. ej. producción).
    """
    app = create_app()

    async def _db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _db
    clientes: list[AsyncClient] = []

    def _nuevo(settings: Settings | None = None) -> AsyncClient:
        if settings is not None:
            app.dependency_overrides[get_settings] = lambda: settings
        cliente = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clientes.append(cliente)
        return cliente

    yield _nuevo
    for cliente in clientes:
        await cliente.aclose()


@pytest.fixture
def client(make_client: ClientFactory) -> AsyncClient:
    return make_client()
