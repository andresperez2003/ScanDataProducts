"""Servicio de autenticación: registro, inicio de sesión e identidad actual."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.errors import (
    DomainValidationError,
    DuplicateCompanyError,
    DuplicateUsernameError,
    InvalidCredentialsError,
    NotAuthenticatedError,
)
from src.core.normalize import normalize_name
from src.core.security import (
    hash_password,
    verify_against_decoy,
    verify_password,
)
from src.models.domain import AuthContext, CompanyData, UserData
from src.repos.company import CompanyRepo
from src.repos.user import UserRepo
from src.services.password_policy import password_error
from src.services.sessions import start_session

REQUIRED_FIELD = "Campo obligatorio."


@dataclass(frozen=True)
class AuthResult:
    """Resultado de registrarse o iniciar sesión: la sesión ya está creada."""

    user: UserData
    company: CompanyData
    # Token en claro: solo para la cookie de la respuesta, nunca se almacena.
    session_token: str


def _register_errors(company_name: str, username: str, password: str) -> dict[str, str]:
    """Errores por campo de CA-1.3 y CA-1.4, todos juntos."""
    errors: dict[str, str] = {}
    if not company_name.strip():
        errors["company_name"] = REQUIRED_FIELD
    if not username.strip():
        errors["username"] = REQUIRED_FIELD
    # La contraseña nunca se recorta: un espacio es un carácter no permitido.
    problema = REQUIRED_FIELD if not password else password_error(password)
    if problema is not None:
        errors["password"] = problema
    return errors


async def register(
    db: AsyncSession, *, company_name: str, username: str, password: str, now: datetime
) -> AuthResult:
    """Crea empresa, primer usuario y su sesión en una sola transacción (CA-1.1).

    Los duplicados los detectan los UNIQUE de la BD, también bajo concurrencia
    (spec §5); la violación se traduce a error de dominio y no se crea nada.
    """
    errors = _register_errors(company_name, username, password)
    if errors:
        raise DomainValidationError(errors)
    password_hash = await hash_password(password)

    try:
        company = await CompanyRepo(db).create(
            uuid.uuid4(),
            name=company_name,
            name_normalized=normalize_name(company_name),
        )
    except IntegrityError:
        await db.rollback()
        raise DuplicateCompanyError() from None
    try:
        user = await UserRepo(db).create(
            company.id,
            username=username,
            username_normalized=normalize_name(username),
            password_hash=password_hash,
            created_by=None,
        )
    except IntegrityError:
        # Deshace también la empresa recién creada (CA-1.2: no se crea nada).
        await db.rollback()
        raise DuplicateUsernameError() from None

    token = await start_session(db, user, now=now)
    await db.commit()
    return AuthResult(user=user, company=company, session_token=token)


async def _authenticate(
    db: AsyncSession, username_normalized: str, password: str
) -> tuple[UserData, CompanyData] | None:
    """Usuario y empresa si las credenciales son válidas; None en cualquier otro caso.

    Cuesta lo mismo en todos los casos: si el usuario no existe se verifica
    contra el hash señuelo (CA-2.3), y al deshabilitado también se le verifica
    la contraseña (CA-2.4).
    """
    user = await UserRepo(db).get_by_username(username_normalized)
    if user is None:
        await verify_against_decoy(password)
        return None
    valid = await verify_password(user.password_hash, password)
    company = await CompanyRepo(db).get(user.company_id)
    if not valid or user.disabled_at is not None or company is None:
        return None
    return user, company


async def login(
    db: AsyncSession, *, username: str, password: str, now: datetime
) -> AuthResult:
    """Inicio de sesión solo con usuario y contraseña (RN-3, CA-2.1).

    Cualquier fallo de credenciales lanza el mismo InvalidCredentialsError
    (RN-6). No hay bloqueo por intentos fallidos: fuera de alcance (spec D-4).
    """
    autenticado = await _authenticate(db, normalize_name(username), password)
    if autenticado is None:
        raise InvalidCredentialsError()

    user, company = autenticado
    token = await start_session(db, user, now=now)
    await db.commit()
    return AuthResult(user=user, company=company, session_token=token)


async def current_identity(
    db: AsyncSession, context: AuthContext
) -> tuple[UserData, CompanyData]:
    """Usuario y empresa de la sesión, leídos siempre con su company_id (RN-8)."""
    user = await UserRepo(db).get(context.company_id, context.user_id)
    company = await CompanyRepo(db).get(context.company_id)
    if user is None or company is None:
        raise NotAuthenticatedError()
    return user, company
