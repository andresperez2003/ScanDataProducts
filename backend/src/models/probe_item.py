import uuid
from datetime import datetime

from sqlalchemy import Text, text
from sqlmodel import Field, SQLModel

from src.models.columns import timestamptz


class ProbeItem(SQLModel, table=True):
    """TEMPORAL (T016): tabla de negocio de prueba para verificar el aislamiento.

    Se elimina, con una migración nueva, al cerrar la spec 002 (plan §4).
    """

    __tablename__ = "probe_items"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    company_id: uuid.UUID = Field(foreign_key="companies.id", index=True)
    name: str = Field(sa_type=Text)
    created_at: datetime = Field(sa_column=timestamptz(server_now=True))
    created_by: uuid.UUID = Field(foreign_key="users.id")
    # Nulo = activo (constitución, principio 4).
    disabled_at: datetime | None = Field(
        default=None, sa_column=timestamptz(nullable=True, index=True)
    )
    disabled_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
