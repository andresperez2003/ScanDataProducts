import asyncio
import unicodedata
from functools import lru_cache

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from src.core.config import get_settings


def normalize_name(value: str) -> str:
    """Forma canónica de un nombre de empresa o de usuario (RN-2, RN-3).

    NFKC + minúsculas + recorte y colapso de espacios. Es la única función que
    decide si dos nombres son "el mismo": se usa igual al buscar y al insertar.
    """
    return " ".join(unicodedata.normalize("NFKC", value).lower().split())


@lru_cache
def _password_hasher() -> PasswordHasher:
    settings = get_settings()
    return PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
        type=Type.ID,
    )


async def hash_password(password: str) -> str:
    """Hash Argon2id codificado, con sal y parámetros incluidos (RN-5)."""
    # Argon2id es CPU deliberadamente costosa (~200 ms): se ejecuta en un hilo para
    # no bloquear el event loop (constitución, Async). asyncio.to_thread y no
    # run_in_threadpool porque este módulo lo usan servicios, que no importan fastapi.
    return await asyncio.to_thread(_password_hasher().hash, password)


def _verify_sync(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher().verify(password_hash, password)
    except VerificationError, InvalidHashError:
        return False


async def verify_password(password_hash: str, password: str) -> bool:
    """True si la contraseña corresponde al hash. Nunca lanza por no coincidir."""
    # Mismo motivo que en hash_password: cálculo bloqueante fuera del event loop.
    return await asyncio.to_thread(_verify_sync, password_hash, password)
