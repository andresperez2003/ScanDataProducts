"""T008: errores de dominio y su mapeo único a HTTP (constitución, principios 3 y 5)."""

import ast
from pathlib import Path

from src.core.errors import (
    HTTP_STATUS,
    CsrfFailedError,
    DomainError,
    DomainValidationError,
    DuplicateCompanyError,
    DuplicateProductNameError,
    DuplicateProductSkuError,
    DuplicateSupplierNameError,
    DuplicateUsernameError,
    InvalidCredentialsError,
    NotAuthenticatedError,
    NotFoundError,
    http_status_for,
)

_SRC = Path(__file__).resolve().parents[2] / "src"


def _todas_las_subclases(base: type[DomainError]) -> set[type[DomainError]]:
    directas = set(base.__subclasses__())
    return directas.union(*(_todas_las_subclases(c) for c in directas))


def test_principio_5_toda_excepcion_de_dominio_tiene_mapeo_http() -> None:
    sin_mapeo = {c.__name__ for c in _todas_las_subclases(DomainError)} - {
        c.__name__ for c in HTTP_STATUS
    }

    assert sin_mapeo == set()


def test_principio_5_codigos_de_error_unicos_y_no_vacios() -> None:
    codigos = [c.code for c in _todas_las_subclases(DomainError)]

    assert all(codigos)
    assert len(codigos) == len(set(codigos))


def test_principio_5_codigos_y_estados_del_contrato() -> None:
    # plan §5: código de error y estado HTTP de cada caso previsto.
    esperados: dict[type[DomainError], tuple[str, int]] = {
        DomainValidationError: ("VALIDATION_ERROR", 400),
        DuplicateCompanyError: ("COMPANY_NAME_TAKEN", 409),
        InvalidCredentialsError: ("INVALID_CREDENTIALS", 401),
        NotAuthenticatedError: ("NOT_AUTHENTICATED", 401),
        DuplicateUsernameError: ("USERNAME_TAKEN", 409),
        NotFoundError: ("NOT_FOUND", 404),
        CsrfFailedError: ("CSRF_FAILED", 403),
    }

    for clase, (codigo, estado) in esperados.items():
        assert (clase.code, HTTP_STATUS[clase]) == (codigo, estado)


def test_002_codigos_y_estados_del_catalogo() -> None:
    # 002 plan §5: los tres conflictos de unicidad del catálogo.
    esperados: dict[type[DomainError], tuple[str, int]] = {
        DuplicateSupplierNameError: ("SUPPLIER_NAME_TAKEN", 409),
        DuplicateProductNameError: ("PRODUCT_NAME_TAKEN", 409),
        DuplicateProductSkuError: ("PRODUCT_SKU_TAKEN", 409),
    }

    for clase, (codigo, estado) in esperados.items():
        assert issubclass(clase, DomainError)
        assert (clase.code, HTTP_STATUS[clase]) == (codigo, estado)


def test_002_los_conflictos_de_catalogo_tienen_mensaje_propio() -> None:
    # A diferencia de NotFoundError, aquí el mensaje sí puede decir qué pasó:
    # el recurso en conflicto es de la propia empresa (RN-8 no aplica).
    for clase in (
        DuplicateSupplierNameError,
        DuplicateProductNameError,
        DuplicateProductSkuError,
    ):
        assert clase().message != ""


def test_principio_5_el_estado_se_obtiene_de_la_instancia() -> None:
    assert http_status_for(DuplicateCompanyError()) == 409
    assert http_status_for(NotFoundError()) == 404


def test_rn_6_credenciales_invalidas_siempre_el_mismo_mensaje() -> None:
    # No admite mensaje propio: ninguna causa puede filtrarse al cliente.
    assert InvalidCredentialsError().message == InvalidCredentialsError().message
    assert InvalidCredentialsError().message != ""


def test_rn_9_no_encontrado_siempre_el_mismo_mensaje() -> None:
    # No admite mensaje propio: no puede revelar si existe en otra empresa.
    assert NotFoundError().message == NotFoundError().message
    assert NotFoundError().message != ""


def test_ca_1_3_error_de_validacion_indica_los_campos() -> None:
    error = DomainValidationError({"company_name": "Campo obligatorio."})

    assert error.fields == {"company_name": "Campo obligatorio."}


def _modulos_que_importa(archivo: Path) -> set[str]:
    modulos: set[str] = set()
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module.split(".")[0])
    return modulos


def test_principio_3_services_y_errores_de_dominio_no_importan_http() -> None:
    # errors.py también: lo importan los servicios.
    archivos = [*(_SRC / "services").rglob("*.py"), _SRC / "core" / "errors.py"]

    infractores = {
        str(a.relative_to(_SRC)): sorted(
            _modulos_que_importa(a) & {"fastapi", "starlette"}
        )
        for a in archivos
        if _modulos_que_importa(a) & {"fastapi", "starlette"}
    }

    assert infractores == {}
