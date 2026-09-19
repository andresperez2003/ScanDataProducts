"""T004: hash de contraseñas y normalización de nombres (spec RN-2, RN-3, RN-5, §5, §7)."""

import time

from src.core.security import hash_password, normalize_name, verify_password

# Cumple RN-4 (D-5): 12+ caracteres, mayúscula, minúscula, número y especial.
_CONTRASENA = "Trazabilidad#2026"


async def test_rn_5_el_hash_no_contiene_la_contrasena() -> None:
    almacenado = await hash_password(_CONTRASENA)

    assert _CONTRASENA not in almacenado
    assert almacenado.startswith("$argon2id$")


async def test_rn_5_la_contrasena_correcta_verifica() -> None:
    almacenado = await hash_password(_CONTRASENA)

    assert await verify_password(almacenado, _CONTRASENA) is True


async def test_rn_5_una_contrasena_incorrecta_no_verifica() -> None:
    almacenado = await hash_password(_CONTRASENA)

    assert await verify_password(almacenado, "Trazabilidad#2027") is False


async def test_rn_5_un_hash_corrupto_no_verifica() -> None:
    assert await verify_password("no-es-un-hash", _CONTRASENA) is False


async def test_rn_5_la_misma_contrasena_produce_hashes_distintos() -> None:
    # Sal aleatoria: un volcado no revela qué usuarios comparten contraseña (§7).
    assert await hash_password(_CONTRASENA) != await hash_password(_CONTRASENA)


async def test_borde_contrasena_de_200_caracteres_hashea_y_verifica() -> None:
    larga = ("Aa1#" * 50)[:200]
    assert len(larga) == 200

    almacenado = await hash_password(larga)

    assert await verify_password(almacenado, larga) is True
    # Sin truncado: cambiar el último carácter la invalida.
    assert await verify_password(almacenado, larga[:-1] + "@") is False


async def test_nfr_7_verificar_tarda_menos_de_400_ms() -> None:
    almacenado = await hash_password(_CONTRASENA)

    inicio = time.perf_counter()
    await verify_password(almacenado, _CONTRASENA)
    transcurrido = time.perf_counter() - inicio

    assert transcurrido < 0.4


def test_borde_rn_2_empresa_que_difiere_en_mayusculas_y_espacios_es_la_misma() -> None:
    assert normalize_name("  Acme   S.A. ") == normalize_name("acme s.a.")
    assert normalize_name("Acme S.A.") == "acme s.a."


def test_rn_2_empresas_distintas_normalizan_distinto() -> None:
    assert normalize_name("Acme S.A.") != normalize_name("Acme S.L.")


def test_borde_rn_3_usuario_que_difiere_en_mayusculas_es_el_mismo() -> None:
    assert normalize_name("Admin") == normalize_name("ADMIN") == "admin"


def test_rn_3_usuarios_distintos_normalizan_distinto() -> None:
    assert normalize_name("admin1") != normalize_name("admin2")


def test_normalizacion_nfkc_unifica_variantes_unicode() -> None:
    # Letras de ancho completo y espacio no separable son "el mismo" texto
    # (plan §7, riesgo de normalización Unicode).
    assert normalize_name("ＡＣＭＥ S.A.") == normalize_name("acme s.a.")
