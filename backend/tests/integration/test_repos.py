"""T007: repositorios (constitución, principios 1, 3 y 4; spec CA-4.1, CA-4.4, RN-7)."""

import importlib
import inspect
import pkgutil
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import ModuleType

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import src.repos
from src.models.domain import CompanyData, SessionData, UserData
from src.repos.company import CompanyRepo
from src.repos.session import SessionRepo
from src.repos.user import UserRepo
from tests.conftest import Tenant

_AHORA = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


# --- companies -------------------------------------------------------------


async def test_principio_3_crear_empresa_devuelve_objeto_de_dominio(
    db_session: AsyncSession,
) -> None:
    company_id = uuid.uuid4()

    empresa = await CompanyRepo(db_session).create(
        company_id, name="Acme S.A.", name_normalized="acme s.a."
    )

    assert isinstance(empresa, CompanyData)
    assert not isinstance(empresa, SQLModel)
    assert (empresa.id, empresa.name, empresa.disabled_at) == (
        company_id,
        "Acme S.A.",
        None,
    )
    assert empresa.created_at.tzinfo is not None


async def test_principio_3_leer_empresa_por_su_company_id(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, _ = two_companies

    leida = await CompanyRepo(db_session).get(empresa_a.company_id)

    assert isinstance(leida, CompanyData)
    assert leida.id == empresa_a.company_id


async def test_ca_4_1_empresa_inexistente_devuelve_none(
    db_session: AsyncSession,
) -> None:
    assert await CompanyRepo(db_session).get(uuid.uuid4()) is None


# --- users -----------------------------------------------------------------


async def test_principio_3_crear_usuario_devuelve_objeto_de_dominio(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, _ = two_companies

    usuario = await UserRepo(db_session).create(
        empresa_a.company_id,
        username="Maria",
        username_normalized="maria",
        password_hash="hash",
        created_by=None,
    )

    assert isinstance(usuario, UserData)
    assert not isinstance(usuario, SQLModel)
    assert (usuario.company_id, usuario.username, usuario.disabled_at) == (
        empresa_a.company_id,
        "Maria",
        None,
    )


async def test_principio_1_leer_usuario_de_su_propia_empresa(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, _ = two_companies

    usuario = await UserRepo(db_session).get(empresa_a.company_id, empresa_a.user_id)

    assert isinstance(usuario, UserData)
    assert usuario.id == empresa_a.user_id


async def test_ca_4_1_usuario_de_a_pedido_con_company_id_de_b_es_none(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, empresa_b = two_companies

    assert (
        await UserRepo(db_session).get(empresa_b.company_id, empresa_a.user_id) is None
    )


async def test_rn_3_buscar_usuario_por_nombre_sin_empresa(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, _ = two_companies

    usuario = await UserRepo(db_session).get_by_username(empresa_a.username.lower())

    assert isinstance(usuario, UserData)
    # El login obtiene la empresa del usuario, no del cliente (CA-2.1).
    assert (usuario.id, usuario.company_id) == (empresa_a.user_id, empresa_a.company_id)


async def test_ca_2_3_buscar_usuario_inexistente_devuelve_none(
    db_session: AsyncSession,
) -> None:
    assert await UserRepo(db_session).get_by_username("nadie") is None


async def test_rn_7_deshabilitar_usuario_conserva_el_registro(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, _ = two_companies
    repo = UserRepo(db_session)

    hecho = await repo.disable(
        empresa_a.company_id,
        empresa_a.user_id,
        disabled_by=empresa_a.user_id,
        at=_AHORA,
    )

    usuario = await repo.get(empresa_a.company_id, empresa_a.user_id)
    assert hecho is True
    assert usuario is not None
    assert usuario.disabled_at == _AHORA


async def test_ca_4_4_deshabilitar_usuario_de_a_con_company_id_de_b_no_lo_cambia(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, empresa_b = two_companies
    repo = UserRepo(db_session)

    hecho = await repo.disable(
        empresa_b.company_id,
        empresa_a.user_id,
        disabled_by=empresa_b.user_id,
        at=_AHORA,
    )

    usuario = await repo.get(empresa_a.company_id, empresa_a.user_id)
    assert hecho is False
    assert usuario is not None
    assert usuario.disabled_at is None


# --- sessions --------------------------------------------------------------


async def _crear_sesion(
    db_session: AsyncSession, tenant: Tenant, token_hash: bytes
) -> SessionData:
    return await SessionRepo(db_session).create(
        tenant.company_id,
        user_id=tenant.user_id,
        token_hash=token_hash,
        created_at=_AHORA,
        absolute_expires_at=_AHORA + timedelta(days=15),
    )


async def test_principio_3_crear_sesion_devuelve_objeto_de_dominio(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, _ = two_companies

    sesion = await _crear_sesion(db_session, empresa_a, b"h" * 32)

    assert isinstance(sesion, SessionData)
    assert not isinstance(sesion, SQLModel)
    assert (sesion.company_id, sesion.user_id) == (
        empresa_a.company_id,
        empresa_a.user_id,
    )
    assert sesion.last_seen_at == _AHORA
    assert sesion.revoked_at is None


async def test_ca_3_1_buscar_sesion_activa_por_hash_del_token(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, _ = two_companies
    creada = await _crear_sesion(db_session, empresa_a, b"a" * 32)

    encontrada = await SessionRepo(db_session).get_active_by_token_hash(b"a" * 32)

    assert encontrada == creada


async def test_ca_3_2_sesion_revocada_ya_no_se_encuentra(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, _ = two_companies
    creada = await _crear_sesion(db_session, empresa_a, b"b" * 32)
    repo = SessionRepo(db_session)

    await repo.revoke(creada.id, at=_AHORA)

    assert await repo.get_active_by_token_hash(b"b" * 32) is None


async def test_ca_3_3_renovar_actividad_de_la_sesion(
    db_session: AsyncSession, two_companies: tuple[Tenant, Tenant]
) -> None:
    empresa_a, _ = two_companies
    creada = await _crear_sesion(db_session, empresa_a, b"c" * 32)
    repo = SessionRepo(db_session)
    despues = _AHORA + timedelta(hours=1)

    await repo.touch(creada.id, at=despues)

    renovada = await repo.get_active_by_token_hash(b"c" * 32)
    assert renovada is not None
    assert renovada.last_seen_at == despues


# --- inspección del código fuente -----------------------------------------

_MARCA_EXCEPCION = "# EXCEPCIÓN: ver plan.md §3"


def _modulos_de_repos() -> list[ModuleType]:
    return [
        importlib.import_module(f"{src.repos.__name__}.{info.name}")
        for info in pkgutil.iter_modules(src.repos.__path__)
    ]


def _usa_tabla_de_negocio(modulo: ModuleType) -> bool:
    """Tabla de negocio = tabla con `disabled_at` (plan §4, Notas de esquema)."""
    return any(
        isinstance(obj, type)
        and issubclass(obj, SQLModel)
        and hasattr(obj, "__table__")
        and "disabled_at" in obj.__table__.columns
        for obj in vars(modulo).values()
    )


def _metodos_publicos(modulo: ModuleType) -> list[tuple[str, Callable[..., object]]]:
    metodos = []
    for clase in vars(modulo).values():
        if not (isinstance(clase, type) and clase.__module__ == modulo.__name__):
            continue
        for nombre, funcion in vars(clase).items():
            if callable(funcion) and not nombre.startswith("_"):
                metodos.append((f"{clase.__name__}.{nombre}", funcion))
    return metodos


def test_principio_1_repos_de_tablas_de_negocio_reciben_company_id_primero() -> None:
    de_negocio = [m for m in _modulos_de_repos() if _usa_tabla_de_negocio(m)]
    # Evita que el test pase en vacío si cambia la detección.
    assert {"src.repos.company", "src.repos.user"} <= {m.__name__ for m in de_negocio}

    incumplen, excepciones = [], []
    for modulo in de_negocio:
        for nombre, metodo in _metodos_publicos(modulo):
            if _MARCA_EXCEPCION in inspect.getsource(metodo):
                excepciones.append(nombre)
                continue
            parametros = list(inspect.signature(metodo).parameters)[1:]  # sin self
            if parametros[:1] != ["company_id"]:
                incumplen.append(nombre)

    assert incumplen == []
    # La única excepción del proyecto es la búsqueda del login (plan §3).
    assert excepciones == ["UserRepo.get_by_username"]
