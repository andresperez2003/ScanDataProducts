import uuid
from datetime import datetime

from sqlalchemy import Column, Computed, Index, Text, Uuid, text
from sqlmodel import Field, SQLModel

from src.models.columns import timestamptz

# Marcador del grupo "sin proveedor" en supplier_key. No es un proveedor real ni
# existe en `suppliers`: solo agrupa, para el índice único, a los productos que no
# tienen proveedor (D-1).
NO_SUPPLIER_KEY = uuid.UUID("00000000-0000-0000-0000-000000000000")

_SUPPLIER_KEY_EXPR = f"COALESCE(supplier_id, '{NO_SUPPLIER_KEY}'::uuid)"


class Product(SQLModel, table=True):
    """Producto de una empresa, con proveedor opcional. Plan §4, tabla `products`."""

    __tablename__ = "products"
    __table_args__ = (
        # RN-2: el nombre es único entre los productos activos del MISMO proveedor
        # (D-2), con los productos sin proveedor como su propio grupo (D-1).
        Index(
            "ux_products_company_supplier_name_active",
            "company_id",
            "supplier_key",
            "name_normalized",
            unique=True,
            postgresql_where=text("disabled_at IS NULL"),
        ),
        # RN-3: misma regla para el SKU, pero solo cuando no está vacío — por eso
        # el índice excluye los nulos (§5, "SKU vacío en dos productos").
        Index(
            "ux_products_company_supplier_sku_active",
            "company_id",
            "supplier_key",
            "sku_normalized",
            unique=True,
            postgresql_where=text("disabled_at IS NULL AND sku_normalized IS NOT NULL"),
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={"server_default": text("gen_random_uuid()")},
    )
    # Principio 1: toda tabla de negocio lleva company_id no nulo, con índice.
    company_id: uuid.UUID = Field(foreign_key="companies.id", index=True)
    # Nulo = sin proveedor (D-1). Opcional por decisión escrita de la spec.
    supplier_id: uuid.UUID | None = Field(
        default=None, foreign_key="suppliers.id", index=True
    )
    # Generada por la BD: existe solo para poder indexar el grupo "sin proveedor"
    # (plan §4). En SQL dos NULL nunca son iguales, así que un índice sobre
    # supplier_id no impediría dos productos sin proveedor con el mismo nombre.
    # Opcional en Python porque nunca se lee ni se escribe desde el código: la
    # calcula Postgres en cada INSERT y UPDATE.
    supplier_key: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid,
            Computed(_SUPPLIER_KEY_EXPR, persisted=True),
            nullable=False,
        ),
    )
    # Tal como lo escribió el usuario (§5, primer caso borde).
    name: str = Field(sa_type=Text)
    # Calculado por el servicio con normalize_name (RN-2).
    name_normalized: str = Field(sa_type=Text)
    # Nulo = sin SKU. El servicio convierte a nulo el SKU vacío, para que la
    # unicidad de RN-3 no lo alcance.
    sku: str | None = Field(default=None, sa_type=Text, nullable=True)
    sku_normalized: str | None = Field(default=None, sa_type=Text, nullable=True)
    created_at: datetime = Field(sa_column=timestamptz(server_now=True))
    created_by: uuid.UUID = Field(foreign_key="users.id")
    # Nulo = activo (constitución, principio 4). Nada se borra.
    disabled_at: datetime | None = Field(
        default=None, sa_column=timestamptz(nullable=True, index=True)
    )
    disabled_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
