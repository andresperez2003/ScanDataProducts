import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, Text, Uuid, text
from sqlmodel import Field, SQLModel

from src.models.columns import timestamptz


class Company(SQLModel, table=True):
    """Empresa (tenant). Plan §4, tabla `companies`."""

    __tablename__ = "companies"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    # Tal como lo escribió el usuario.
    name: str = Field(sa_type=Text)
    # Calculado por el servicio con la función de normalización compartida (RN-2).
    name_normalized: str = Field(sa_type=Text, unique=True)
    created_at: datetime = Field(sa_column=timestamptz(server_now=True))
    # Nulo = activa (constitución, principio 4).
    disabled_at: datetime | None = Field(
        default=None, sa_column=timestamptz(nullable=True, index=True)
    )
    # FK circular con users: se añade después de crear ambas tablas y es diferida
    # para poder crear empresa y primer usuario en la misma transacción (plan §4).
    disabled_by: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid,
            ForeignKey(
                "users.id",
                name="fk_companies_disabled_by_users",
                use_alter=True,
                deferrable=True,
                initially="DEFERRED",
            ),
            nullable=True,
        ),
    )
