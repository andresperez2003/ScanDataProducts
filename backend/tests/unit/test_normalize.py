"""T002: normalización de nombres (001 RN-2, RN-3; 002 RN-1, RN-2, RN-3).

Estos casos venían de `test_security.py`: se mueven junto con la función, que
dejó de ser exclusiva de auth al usarla también proveedores y productos (plan §2).
"""

from src.core.normalize import normalize_name


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
    # (001 plan §7, riesgo de normalización Unicode).
    assert normalize_name("ＡＣＭＥ S.A.") == normalize_name("acme s.a.")


# --- 002: los mismos casos borde, ahora sobre catálogo (§5, RN-1 a RN-3) ---


def test_borde_rn_1_proveedor_que_difiere_en_mayusculas_y_espacios_es_el_mismo() -> (
    None
):
    # §5, primer caso borde: "Tornillo 5mm" vs "  tornillo   5mm ".
    assert normalize_name("Tornillo 5mm") == normalize_name("  tornillo   5mm ")


def test_borde_rn_3_sku_que_difiere_en_mayusculas_y_espacios_es_el_mismo() -> None:
    # §5, segundo caso borde: el SKU se compara igual que el nombre.
    assert normalize_name("TOR-5MM") == normalize_name(" tor-5mm ")


def test_borde_texto_en_blanco_normaliza_a_cadena_vacia() -> None:
    # Lo que permite al servicio tratar "   " como ausencia de valor.
    assert normalize_name("   ") == ""
