"""T005: token de sesión, su hash y su firma (spec §7 Seguridad, CA-3.2; plan §2)."""

import base64
import hashlib

from itsdangerous import Signer

from src.core.security import (
    generate_session_token,
    hash_session_token,
    sign_session_token,
    unsign_session_token,
)


def _bytes_del_token(token: str) -> bytes:
    return base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))


def test_nfr_7_dos_tokens_generados_nunca_coinciden() -> None:
    tokens = {generate_session_token() for _ in range(1000)}

    assert len(tokens) == 1000


def test_nfr_7_el_token_tiene_32_bytes_aleatorios() -> None:
    assert len(_bytes_del_token(generate_session_token())) == 32


def test_ca_3_2_el_hash_del_token_es_determinista() -> None:
    token = generate_session_token()

    assert hash_session_token(token) == hash_session_token(token)


def test_ca_3_2_el_hash_es_sha256_del_token() -> None:
    token = generate_session_token()

    assert hash_session_token(token) == hashlib.sha256(token.encode()).digest()


def test_ca_3_2_tokens_distintos_dan_hashes_distintos() -> None:
    assert hash_session_token(generate_session_token()) != hash_session_token(
        generate_session_token()
    )


def test_nfr_7_un_token_firmado_se_recupera_intacto() -> None:
    token = generate_session_token()

    assert unsign_session_token(sign_session_token(token)) == token


def test_nfr_7_una_firma_manipulada_se_rechaza() -> None:
    firmado = sign_session_token(generate_session_token())
    ultimo = firmado[-1]
    manipulado = firmado[:-1] + ("A" if ultimo != "A" else "B")

    assert unsign_session_token(manipulado) is None


def test_nfr_7_un_token_manipulado_con_su_firma_original_se_rechaza() -> None:
    token = generate_session_token()
    _, firma = sign_session_token(token).rsplit(".", 1)
    otro_token = generate_session_token()

    assert unsign_session_token(f"{otro_token}.{firma}") is None


def test_nfr_7_un_token_firmado_con_otro_secreto_se_rechaza() -> None:
    ajeno = Signer("otro-secreto-de-al-menos-32-caracteres!").sign("abc").decode()

    assert unsign_session_token(ajeno) is None


def test_nfr_7_un_valor_sin_firma_se_rechaza() -> None:
    assert unsign_session_token(generate_session_token()) is None
    assert unsign_session_token("") is None
