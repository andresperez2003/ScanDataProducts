import asyncio
import hashlib
import secrets
import unicodedata
from functools import lru_cache

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from itsdangerous import BadSignature, Signer

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


@lru_cache
def _decoy_hash() -> str:
    """Hash señuelo de una contraseña aleatoria que nadie conoce (plan §5)."""
    return _password_hasher().hash(secrets.token_urlsafe(32))


def _verify_decoy_sync(password: str) -> None:
    _verify_sync(_decoy_hash(), password)


async def warm_decoy_hash() -> None:
    """Genera el hash señuelo al arrancar, para que el primer login no tarde más."""
    await asyncio.to_thread(_decoy_hash)


async def verify_against_decoy(password: str) -> None:
    """Gasta el mismo tiempo que una verificación real cuando el usuario no existe.

    Sin esto, la diferencia de tiempo revela qué usuarios existen (CA-2.3).
    """
    # Mismo motivo que en hash_password: cálculo bloqueante fuera del event loop.
    await asyncio.to_thread(_verify_decoy_sync, password)


_SESSION_TOKEN_BYTES = 32


def generate_session_token() -> str:
    """Token opaco de sesión: 32 bytes aleatorios en base64 URL-safe (plan §2)."""
    return secrets.token_urlsafe(_SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> bytes:
    """SHA-256 del token: lo único que se guarda en `sessions.token_hash`.

    Un volcado de la BD no permite suplantar sesiones (plan §4).
    """
    return hashlib.sha256(token.encode()).digest()


@lru_cache
def _session_signer() -> Signer:
    # El salt separa esta firma de cualquier otro uso futuro del mismo secreto.
    return Signer(get_settings().session_secret, salt="session-cookie")


def sign_session_token(token: str) -> str:
    """Valor de la cookie `session`: el token con su firma HMAC."""
    return _session_signer().sign(token).decode()


def unsign_session_token(signed: str) -> str | None:
    """El token si la firma es válida; None si falta o fue manipulada."""
    try:
        return _session_signer().unsign(signed).decode()
    except BadSignature:
        return None
