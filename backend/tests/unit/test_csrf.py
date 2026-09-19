"""T006: protección CSRF double-submit (spec §5 último caso borde, §7 Seguridad; plan §5)."""

from http.cookies import SimpleCookie

from starlette.responses import Response

from src.core.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    generate_csrf_token,
    is_valid_csrf,
    set_csrf_cookie,
)


def _set_cookie_header(secure: bool) -> tuple[str, str]:
    response = Response()
    token = generate_csrf_token()
    set_csrf_cookie(response, token, secure=secure)
    return token, response.headers["set-cookie"]


def test_nfr_7_cookie_y_cabecera_iguales_pasa() -> None:
    token = generate_csrf_token()

    assert is_valid_csrf(cookie_value=token, header_value=token) is True


def test_borde_peticion_sin_cabecera_csrf_se_rechaza() -> None:
    assert is_valid_csrf(cookie_value=generate_csrf_token(), header_value=None) is False


def test_borde_peticion_sin_cookie_csrf_se_rechaza() -> None:
    assert is_valid_csrf(cookie_value=None, header_value=generate_csrf_token()) is False


def test_borde_cookie_y_cabecera_distintas_se_rechaza() -> None:
    assert (
        is_valid_csrf(
            cookie_value=generate_csrf_token(), header_value=generate_csrf_token()
        )
        is False
    )


def test_borde_cookie_y_cabecera_vacias_se_rechaza() -> None:
    assert is_valid_csrf(cookie_value="", header_value="") is False


def test_nfr_7_los_tokens_csrf_no_se_repiten() -> None:
    assert len({generate_csrf_token() for _ in range(1000)}) == 1000


def test_nfr_7_nombres_de_cookie_y_cabecera_del_contrato() -> None:
    assert CSRF_COOKIE_NAME == "csrf_token"
    assert CSRF_HEADER_NAME == "X-CSRF-Token"


def test_nfr_7_cookie_csrf_legible_por_el_frontend_y_samesite_lax() -> None:
    token, cabecera = _set_cookie_header(secure=True)
    cookie = SimpleCookie(cabecera)[CSRF_COOKIE_NAME]

    assert cookie.value == token
    # Sin HttpOnly: el frontend la copia a la cabecera X-CSRF-Token (plan §5).
    assert "httponly" not in cabecera.lower()
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"


def test_nfr_7_cookie_csrf_secure_segun_se_indique() -> None:
    _, con_secure = _set_cookie_header(secure=True)
    _, sin_secure = _set_cookie_header(secure=False)

    assert "secure" in con_secure.lower()
    assert "secure" not in sin_secure.lower()
