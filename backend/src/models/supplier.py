import uuid
from datetime import datetime

from sqlalchemy import Index, Text, text
from sqlmodel import Field, SQLModel

from src.models.columns import timestamptz


class Supplier(SQLModel, table=True):
    """Proveedor de una empresa. Plan §4, tabla `suppliers`."""

    __tablename__ = "suppliers"
    __table_args__ = (
        # RN-1: el nombre es único entre los proveedores ACTIVOS de la empresa.
        # Parcial: un nombre liberado al deshabilitar vuelve a estar disponible,
        # y rehabilitar con conflicto falla igual que un alta duplicada (D-4).
        Index(
            "ux_suppliers_company_name_active",
            "company_id",
            "name_normalized",
            unique=True,
            postgresql_where=text("disabled_at IS NULL"),
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    # Principio 1: toda tabla de negocio lleva company_id no nulo, con índice.
    company_id: uuid.UUID = Field(foreign_key="companies.id", index=True)
    # Tal como lo escribió el usuario (§5, primer caso borde).
    name: str = Field(sa_type=Text)
    # Calculado por el servicio con normalize_name: decide si dos nombres son
    # "el mismo" a efectos de RN-1.
    name_normalized: str = Field(sa_type=Text)
    created_at: datetime = Field(sa_column=timestamptz(server_now=True))
    created_by: uuid.UUID = Field(foreign_key="users.id")
    # Nulo = activo (constitución, principio 4). Nada se borra.
    disabled_at: datetime | None = Field(
        default=None, sa_column=timestamptz(nullable=True, index=True)
    )
    disabled_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
