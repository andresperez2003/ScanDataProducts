import secrets

from starlette.responses import Response

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(
    response: Response, token: str, *, secure: bool, max_age: int | None = None
) -> None:
    """Emite la cookie `csrf_token` con los flags del contrato (plan §5).

    Sin HttpOnly a propósito: el frontend la lee y la copia a `X-CSRF-Token`.
    `secure` lo decide quien llama según el entorno. `max_age` debe coincidir con
    el de la cookie de sesión: sin ella no se podría cerrar sesión.
    """
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )


def is_valid_csrf(*, cookie_value: str | None, header_value: str | None) -> bool:
    """Double-submit: la cabecera debe repetir el valor de la cookie."""
    if not cookie_value or not header_value:
        return False
    # Comparación en tiempo constante: no revela cuántos caracteres coinciden.
    return secrets.compare_digest(cookie_value, header_value)
