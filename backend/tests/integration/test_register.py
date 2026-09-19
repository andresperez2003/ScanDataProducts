"""T009: registro de empresa y primer usuario (spec HU-1, CA-1.1 a CA-1.5, §5)."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.db import get_sessionmaker
from src.core.errors import (
    DomainValidationError,
    DuplicateCompanyError,
    DuplicateUsernameError,
)
from src.core.security import verify_password
from src.models import Company, Session, User
from src.services.auth import register
from src.services.password_policy import PasswordRequirement

_CONTRASENA = "Trazabilidad#2026"
_AHORA = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


async def _empresas_con_nombre(db: AsyncSession, normalizado: str) -> int:
    consulta = select(func.count()).where(Company.name_normalized == normalizado)
    return (await db.exec(consulta)).one()


async def _usuarios_con_nombre(db: AsyncSession, normalizado: str) -> int:
    consulta = select(func.count()).where(User.username_normalized == normalizado)
    return (await db.exec(consulta)).one()


async def test_ca_1_1_registro_crea_empresa_y_usuario_asociado(
    db_session: AsyncSession,
) -> None:
    resultado = await register(
        db_session,
        company_name="Acme S.A.",
        username="Maria",
        password=_CONTRASENA,
        now=_AHORA,
    )

    assert resultado.company.name == "Acme S.A."
    assert resultado.user.username == "Maria"
    assert resultado.user.company_id == resultado.company.id
    guardado = await db_session.get(User, resultado.user.id)
    assert guardado is not None
    assert guardado.company_id == resultado.company.id


async def test_ca_1_2_empresa_existente_se_rechaza_sin_crear_nada(
    db_session: AsyncSession,
) -> None:
    await register(
        db_session,
        company_name="Acme S.A.",
        username="maria",
        password=_CONTRASENA,
        now=_AHORA,
    )

    with pytest.raises(DuplicateCompanyError):
        await register(
            db_session,
            company_name="Acme S.A.",
            username="pedro",
            password=_CONTRASENA,
            now=_AHORA,
        )

    assert await _empresas_con_nombre(db_session, "acme s.a.") == 1
    assert await _usuarios_con_nombre(db_session, "pedro") == 0


async def test_borde_empresa_que_difiere_en_mayusculas_y_espacios_es_duplicada(
    db_session: AsyncSession,
) -> None:
    primera = await register(
        db_session,
        company_name="Acme S.A.",
        username="maria",
        password=_CONTRASENA,
        now=_AHORA,
    )

    with pytest.raises(DuplicateCompanyError):
        await register(
            db_session,
            company_name="  acme   s.a. ",
            username="pedro",
            password=_CONTRASENA,
            now=_AHORA,
        )

    # El nombre se almacena tal como lo escribió el usuario.
    assert primera.company.name == "Acme S.A."


async def test_borde_usuario_que_difiere_en_mayusculas_se_rechaza_sin_crear_nada(
    db_session: AsyncSession,
) -> None:
    await register(
        db_session,
        company_name="Empresa Uno",
        username="Admin",
        password=_CONTRASENA,
        now=_AHORA,
    )

    with pytest.raises(DuplicateUsernameError):
        await register(
            db_session,
            company_name="Empresa Dos",
            username="ADMIN",
            password=_CONTRASENA,
            now=_AHORA,
        )

    # La empresa del segundo intento tampoco se crea.
    assert await _empresas_con_nombre(db_session, "empresa dos") == 0
    assert await _usuarios_con_nombre(db_session, "admin") == 1


@pytest.mark.parametrize(
    ("campos", "vacio"),
    [
        ({"company_name": "", "username": "maria"}, "company_name"),
        ({"company_name": "Acme", "username": ""}, "username"),
        ({"company_name": "   ", "username": "maria"}, "company_name"),
        ({"company_name": "Acme", "username": "   "}, "username"),
    ],
    ids=["empresa", "usuario", "empresa-solo-espacios", "usuario-solo-espacios"],
)
async def test_ca_1_3_campo_vacio_indica_cual_falta_sin_crear_nada(
    db_session: AsyncSession, campos: dict[str, str], vacio: str
) -> None:
    with pytest.raises(DomainValidationError) as error:
        await register(db_session, password=_CONTRASENA, **campos, now=_AHORA)

    assert set(error.value.fields) == {vacio}
    assert await _usuarios_con_nombre(db_session, "maria") == 0
    assert await _empresas_con_nombre(db_session, "acme") == 0


async def test_ca_1_3_contrasena_vacia_indica_el_campo(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(DomainValidationError) as error:
        await register(
            db_session, company_name="Acme", username="maria", password="", now=_AHORA
        )

    assert set(error.value.fields) == {"password"}


async def test_ca_1_3_todos_los_campos_vacios_se_indican_juntos(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(DomainValidationError) as error:
        await register(
            db_session, company_name="", username="", password="", now=_AHORA
        )

    assert set(error.value.fields) == {"company_name", "username", "password"}


async def test_ca_1_4_contrasena_invalida_indica_el_requisito_sin_crear_nada(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(DomainValidationError) as error:
        await register(
            db_session,
            company_name="Acme",
            username="maria",
            password="Corta#1",
            now=_AHORA,
        )

    assert PasswordRequirement.MIN_LENGTH.message in error.value.fields["password"]
    assert await _empresas_con_nombre(db_session, "acme") == 0


async def test_ca_1_5_la_contrasena_solo_se_guarda_como_hash_argon2id(
    db_session: AsyncSession,
) -> None:
    resultado = await register(
        db_session,
        company_name="Acme",
        username="maria",
        password=_CONTRASENA,
        now=_AHORA,
    )

    guardado = await db_session.get(User, resultado.user.id)
    assert guardado is not None
    assert guardado.password_hash.startswith("$argon2id$")
    assert _CONTRASENA not in guardado.password_hash
    assert await verify_password(guardado.password_hash, _CONTRASENA)


async def test_borde_contrasena_de_200_caracteres_se_acepta(
    db_session: AsyncSession,
) -> None:
    larga = ("Aa1#" * 50)[:200]

    resultado = await register(
        db_session, company_name="Acme", username="maria", password=larga, now=_AHORA
    )

    assert await verify_password(resultado.user.password_hash, larga)


# --- concurrencia: necesita transacciones reales e independientes ----------


@pytest.fixture
async def nombre_unico() -> AsyncIterator[str]:
    """Nombre de empresa exclusivo del test. Borra lo creado al terminar.

    Los dos registros deben confirmar de verdad para competir por el UNIQUE, así
    que este test no puede usar la transacción revertida de `db_session`.
    """
    sufijo = uuid.uuid4().hex[:8]
    yield sufijo
    async with get_sessionmaker()() as db:
        empresas = select(Company.id).where(
            col(Company.name_normalized) == f"concurrente {sufijo}"
        )
        # El registro también crea la sesión (CA-1.1): se borra antes que el usuario.
        await db.exec(delete(Session).where(col(Session.company_id).in_(empresas)))
        await db.exec(delete(User).where(col(User.company_id).in_(empresas)))
        await db.exec(
            delete(Company).where(
                col(Company.name_normalized) == f"concurrente {sufijo}"
            )
        )
        await db.commit()


async def test_borde_registros_simultaneos_con_el_mismo_nombre(
    nombre_unico: str,
) -> None:
    async def registrar(usuario: str) -> object:
        async with get_sessionmaker()() as db:
            return await register(
                db,
                company_name=f"Concurrente {nombre_unico}",
                username=f"{usuario}-{nombre_unico}",
                password=_CONTRASENA,
                now=_AHORA,
            )

    resultados = await asyncio.gather(
        registrar("uno"), registrar("dos"), return_exceptions=True
    )

    errores = [r for r in resultados if isinstance(r, BaseException)]
    assert len(errores) == 1
    # El perdedor recibe el error de duplicado, nunca un error interno.
    assert isinstance(errores[0], DuplicateCompanyError)
