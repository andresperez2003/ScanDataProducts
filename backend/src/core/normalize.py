"""Forma canónica de un nombre, compartida por auth y catálogo.

Vivía en `core/security.py` mientras solo la usaba el registro; al necesitarla
también proveedores y productos dejó de ser un asunto de seguridad (plan §2 de
002). Es la única función que decide si dos nombres son "el mismo".
"""

import unicodedata


def normalize_name(value: str) -> str:
    """NFKC + minúsculas + recorte y colapso de espacios.

    Se usa igual al buscar y al insertar: 001 RN-2 y RN-3 (empresa y usuario),
    002 RN-1 a RN-3 (nombre de proveedor, nombre y SKU de producto).
    """
    return " ".join(unicodedata.normalize("NFKC", value).lower().split())
