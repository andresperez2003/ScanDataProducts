"""T010: política de contraseñas (spec RN-4, D-5, CA-1.4 y casos borde de §5)."""

import pytest

from src.core.errors import DomainValidationError
from src.services.password_policy import (
    PasswordRequirement,
    check_password,
    validate_password,
)

R = PasswordRequirement
_VALIDA = "Trazabilidad#2026"


def test_rn_4_una_contrasena_que_cumple_todo_es_valida() -> None:
    assert check_password(_VALIDA) == []


def test_rn_4_once_caracteres_no_bastan() -> None:
    assert check_password("Abcdefgh1#x") == [R.MIN_LENGTH]


def test_rn_4_doce_caracteres_bastan() -> None:
    assert check_password("Abcdefgh1#xy") == []


def test_rn_4_falta_mayuscula() -> None:
    assert check_password("trazabilidad#2026") == [R.UPPERCASE]


def test_rn_4_falta_minuscula() -> None:
    assert check_password("TRAZABILIDAD#2026") == [R.LOWERCASE]


def test_rn_4_falta_numero() -> None:
    assert check_password("Trazabilidad#Lotes") == [R.DIGIT]


def test_rn_4_falta_caracter_especial() -> None:
    assert check_password("Trazabilidad2026") == [R.SPECIAL]


@pytest.mark.parametrize("especial", list("#$%&*_@"))
def test_rn_4_cada_especial_de_la_lista_es_valido(especial: str) -> None:
    assert check_password(f"Trazabilidad{especial}2026") == []


@pytest.mark.parametrize(
    "contrasena",
    [" Trazabilidad#2026", "Trazabilidad#2026 ", "Traza bilidad#2026"],
    ids=["inicio", "final", "medio"],
)
def test_borde_contrasena_con_espacio_se_rechaza(contrasena: str) -> None:
    assert check_password(contrasena) == [R.ALLOWED_CHARACTERS]


def test_borde_contrasena_con_enie_se_rechaza() -> None:
    assert check_password("Contraseña#2026") == [R.ALLOWED_CHARACTERS]


def test_borde_letra_acentuada_se_rechaza() -> None:
    assert check_password("Trazabilidád#2026") == [R.ALLOWED_CHARACTERS]


def test_borde_letras_no_ascii_no_cuentan_como_mayuscula_ni_minuscula() -> None:
    # Sin ninguna letra ASCII: Ñ, Á, ñ, á... no cuentan como mayúscula ni minúscula.
    assert check_password("ÑÁÉÍÓÚ#2026ñáéíóú") == [
        R.UPPERCASE,
        R.LOWERCASE,
        R.ALLOWED_CHARACTERS,
    ]


def test_borde_simbolo_fuera_de_la_lista_se_rechaza_aunque_haya_uno_valido() -> None:
    assert check_password("MiClave-2026#") == [R.ALLOWED_CHARACTERS]


def test_borde_contrasena_de_200_caracteres_valida() -> None:
    larga = ("Aa1#" * 50)[:200]

    assert check_password(larga) == []


def test_ca_1_4_contrasena_valida_no_lanza() -> None:
    validate_password(_VALIDA)


def test_ca_1_4_el_rechazo_indica_cada_requisito_incumplido() -> None:
    with pytest.raises(DomainValidationError) as error:
        validate_password("corta")

    mensaje = error.value.fields["password"]
    for requisito in (R.MIN_LENGTH, R.UPPERCASE, R.DIGIT, R.SPECIAL):
        assert requisito.message in mensaje
    assert R.LOWERCASE.message not in mensaje


def test_rn_5_el_mensaje_de_rechazo_no_contiene_la_contrasena() -> None:
    contrasena = "secreto-sin-mayusculas"

    with pytest.raises(DomainValidationError) as error:
        validate_password(contrasena)

    assert contrasena not in error.value.fields["password"]
    assert contrasena not in str(error.value)
