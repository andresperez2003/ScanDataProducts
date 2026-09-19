import uuid
from datetime import datetime

from sqlalchemy import Text, text
from sqlmodel import Field, SQLModel

from src.models.columns import timestamptz


class User(SQLModel, table=True):
    """Usuario de una empresa. Plan §4, tabla `users`."""

    __tablename__ = "users"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    # RN-1: un usuario pertenece a exactamente una empresa.
    company_id: uuid.UUID = Field(foreign_key="companies.id", index=True)
    # Tal como lo escribió el usuario.
    username: str = Field(sa_type=Text)
    # Único en todo el sistema, no por empresa (D-1, RN-3).
    username_normalized: str = Field(sa_type=Text, unique=True)
    # Argon2id codificado, con sal y parámetros. Nunca la contraseña en claro (RN-5).
    password_hash: str = Field(sa_type=Text)
    created_at: datetime = Field(sa_column=timestamptz(server_now=True))
    # Nulo solo en el usuario que se autorregistra (plan §4).
    created_by: uuid.UUID | None = Field(default=None)
    # Nulo = activo (constitución, principio 4).
    disabled_at: datetime | None = Field(
        default=None, sa_column=timestamptz(nullable=True, index=True)
    )
    disabled_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
