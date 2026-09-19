import uuid
from datetime import datetime

from sqlalchemy import Index, LargeBinary, text
from sqlmodel import Field, SQLModel

from src.models.columns import timestamptz


class Session(SQLModel, table=True):
    """Sesión de servidor. Plan §4, tabla `sessions`. No es entidad de negocio."""

    __tablename__ = "sessions"
    __table_args__ = (
        # Búsqueda de cada petición: solo sesiones no revocadas (CA-3.2).
        Index(
            "ix_sessions_token_hash_active",
            "token_hash",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    # Desnormalizado: evita un JOIN en cada petición (§7, < 50 ms).
    company_id: uuid.UUID
    # SHA-256 del token de 32 bytes. El token en claro nunca se almacena.
    token_hash: bytes = Field(sa_type=LargeBinary, unique=True)
    created_at: datetime = Field(sa_column=timestamptz())
    # Se renueva en cada petición; caducidad por inactividad (CA-3.3).
    last_seen_at: datetime = Field(sa_column=timestamptz())
    # created_at + 15 días, sin importar la actividad (D-3, CA-3.5).
    absolute_expires_at: datetime = Field(sa_column=timestamptz())
    # Cierre de sesión (CA-3.2).
    revoked_at: datetime | None = Field(
        default=None, sa_column=timestamptz(nullable=True)
    )
