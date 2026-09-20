"""catalogo: suppliers y products con indices unicos parciales

Revision ID: 35292009efa2
Revises: c24b02cadd6e
Create Date: 2026-09-19 18:26:15.573430

Generada con --autogenerate y revisada a mano (T001, plan §7): esta vez sí
detectó la columna generada `supplier_key` y los tres índices únicos parciales.
Lo revisado, uno por uno:

- `supplier_key` es `GENERATED ALWAYS AS ... STORED` sobre el COALESCE de plan §4,
  y `NOT NULL`: el COALESCE nunca devuelve nulo.
- Los tres índices son `UNIQUE` y parciales, con la condición de plan §4.
- El de SKU excluye además los nulos, para que dos productos sin SKU no choquen.
- Las FK de `company_id`, `supplier_id`, `created_by` y `disabled_by` están todas.
- `downgrade` deja la base como estaba: ningún índice ni tabla se queda atrás.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "35292009efa2"
down_revision: str | Sequence[str] | None = "c24b02cadd6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Marcador del grupo "sin proveedor" (D-1). Ver src/models/product.py.
SUPPLIER_KEY = "COALESCE(supplier_id, '00000000-0000-0000-0000-000000000000'::uuid)"
ACTIVOS = "disabled_at IS NULL"
ACTIVOS_CON_SKU = "disabled_at IS NULL AND sku_normalized IS NOT NULL"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "suppliers",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_normalized", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["disabled_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_suppliers_company_id"), "suppliers", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_suppliers_disabled_at"), "suppliers", ["disabled_at"], unique=False
    )
    # RN-1: nombre único entre los proveedores activos de la empresa.
    op.create_index(
        "ux_suppliers_company_name_active",
        "suppliers",
        ["company_id", "name_normalized"],
        unique=True,
        postgresql_where=sa.text(ACTIVOS),
    )
    op.create_table(
        "products",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
        sa.Column(
            "supplier_key",
            sa.Uuid(),
            sa.Computed(SUPPLIER_KEY, persisted=True),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_normalized", sa.Text(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("sku_normalized", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["disabled_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_products_company_id"), "products", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_products_disabled_at"), "products", ["disabled_at"], unique=False
    )
    op.create_index(
        op.f("ix_products_supplier_id"), "products", ["supplier_id"], unique=False
    )
    # RN-2: nombre único entre los productos activos del mismo proveedor (D-1, D-2).
    op.create_index(
        "ux_products_company_supplier_name_active",
        "products",
        ["company_id", "supplier_key", "name_normalized"],
        unique=True,
        postgresql_where=sa.text(ACTIVOS),
    )
    # RN-3: igual para el SKU, salvo cuando está vacío (§5, último caso borde).
    op.create_index(
        "ux_products_company_supplier_sku_active",
        "products",
        ["company_id", "supplier_key", "sku_normalized"],
        unique=True,
        postgresql_where=sa.text(ACTIVOS_CON_SKU),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ux_products_company_supplier_sku_active",
        table_name="products",
        postgresql_where=sa.text(ACTIVOS_CON_SKU),
    )
    op.drop_index(
        "ux_products_company_supplier_name_active",
        table_name="products",
        postgresql_where=sa.text(ACTIVOS),
    )
    op.drop_index(op.f("ix_products_supplier_id"), table_name="products")
    op.drop_index(op.f("ix_products_disabled_at"), table_name="products")
    op.drop_index(op.f("ix_products_company_id"), table_name="products")
    op.drop_table("products")
    op.drop_index(
        "ux_suppliers_company_name_active",
        table_name="suppliers",
        postgresql_where=sa.text(ACTIVOS),
    )
    op.drop_index(op.f("ix_suppliers_disabled_at"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_company_id"), table_name="suppliers")
    op.drop_table("suppliers")
