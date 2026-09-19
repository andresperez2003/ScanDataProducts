"""/api/v1/auth/*: traducción HTTP de los servicios de autenticación (plan §5)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings, get_settings
from src.core.csrf import CSRF_COOKIE_NAME, generate_csrf_token, set_csrf_cookie
from src.core.db import get_db
from src.core.deps import (
    SESSION_COOKIE_NAME,
    get_auth_context,
    get_session_token,
    require_csrf,
)
from src.core.security import sign_session_token
from src.models.domain import AuthContext, CompanyData, UserData
from src.models.schemas.auth import (
    AuthResponse,
    CompanyOut,
    LoginRequest,
    RegisterRequest,
    UserOut,
)
from src.services import auth
from src.services.sessions import end_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

Db = Annotated[AsyncSession, Depends(get_db)]
CurrentSettings = Annotated[Settings, Depends(get_settings)]


def _secure(settings: Settings) -> bool:
    # Secure se desactiva solo en desarrollo, para usar http://localhost (plan §5).
    return settings.environment != "development"


def _set_auth_cookies(response: Response, token: str, settings: Settings) -> None:
    max_age = settings.session_max_age_days * 24 * 60 * 60
    response.set_cookie(
        SESSION_COOKIE_NAME,
        sign_session_token(token),
        httponly=True,
        secure=_secure(settings),
        samesite="lax",
        path="/",
        max_age=max_age,
    )
    set_csrf_cookie(
        response, generate_csrf_token(), secure=_secure(settings), max_age=max_age
    )


def _auth_response(user: UserData, company: CompanyData) -> AuthResponse:
    return AuthResponse(
        user=UserOut(id=user.id, username=user.username),
        company=CompanyOut(id=company.id, name=company.name),
    )


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest, response: Response, db: Db, settings: CurrentSettings
) -> AuthResponse:
    result = await auth.register(
        db,
        company_name=body.company_name,
        username=body.username,
        password=body.password,
        now=datetime.now(UTC),
    )
    _set_auth_cookies(response, result.session_token, settings)
    return _auth_response(result.user, result.company)


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    db: Db,
    settings: CurrentSettings,
) -> AuthResponse:
    result = await auth.login(
        db,
        username=body.username,
        password=body.password,
        now=datetime.now(UTC),
    )
    _set_auth_cookies(response, result.session_token, settings)
    return _auth_response(result.user, result.company)


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(
    token: Annotated[str, Depends(get_session_token)],
    db: Db,
    settings: CurrentSettings,
) -> Response:
    await end_session(db, token, now=datetime.now(UTC))
    response = Response(status_code=204)
    for nombre in (SESSION_COOKIE_NAME, CSRF_COOKIE_NAME):
        response.delete_cookie(
            nombre, path="/", secure=_secure(settings), samesite="lax"
        )
    return response


@router.get("/me")
async def me(
    context: Annotated[AuthContext, Depends(get_auth_context)], db: Db
) -> AuthResponse:
    user, company = await auth.current_identity(db, context)
    return _auth_response(user, company)
