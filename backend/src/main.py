from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import get_settings
from src.core.csrf import CSRF_HEADER_NAME
from src.core.logging import RequestLoggingMiddleware, configure_logging
from src.core.security import warm_decoy_hash
from src.routers.auth import router as auth_router
from src.routers.errors import register_error_handlers
from src.routers.products import router as products_router
from src.routers.suppliers import router as suppliers_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # El hash señuelo se genera al arrancar: el primer login con usuario
    # inexistente no debe tardar más que los demás (CA-2.3).
    await warm_decoy_hash()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Trazabilidad de Lotes", lifespan=lifespan)
    # El frontend (otro origen) envía cookies y la cabecera CSRF (plan §2).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            o.strip() for o in settings.allowed_origins.split(",") if o.strip()
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", CSRF_HEADER_NAME],
    )
    # Añadido el último: es el más externo y cubre también las respuestas CORS.
    app.add_middleware(RequestLoggingMiddleware)
    register_error_handlers(app)
    app.include_router(auth_router)
    app.include_router(suppliers_router)
    app.include_router(products_router)
    return app


app = create_app()
