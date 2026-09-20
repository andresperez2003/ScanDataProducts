"""T004: hash de contraseñas (spec RN-5, §5, §7).

La normalización de nombres se movió a `test_normalize.py` con la función
(002 T002, plan §2).
"""

import time

from src.core.security import hash_password, verify_password

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
