import uuid
from datetime import datetime

from sqlalchemy import Index, Text, text
from sqlalchemy.dialects.postgresql import INET
from sqlmodel import Field, SQLModel

from src.models.columns import timestamptz


class LoginAttempt(SQLModel, table=True):
    """Intento de inicio de sesión. Plan §4, tabla `login_attempts`.

    No es entidad de negocio: sin `company_id` ni `disabled_at`.
    """

    __tablename__ = "login_attempts"
    __table_args__ = (
        # Ventana por usuario (CA-2.5).
        Index(
            "ix_login_attempts_username_attempted_at",
            "username_normalized",
            "attempted_at",
        ),
        # Ventana por origen (CA-2.6).
        Index("ix_login_attempts_client_ip_attempted_at", "client_ip", "attempted_at"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    # Se registra aunque el usuario no exista.
    username_normalized: str = Field(sa_type=Text)
    client_ip: str = Field(sa_type=INET)
    succeeded: bool
    attempted_at: datetime = Field(sa_column=timestamptz(index=True))
