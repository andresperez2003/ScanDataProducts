"""retirar probe_items: sonda temporal de 001 ya cubierta por el catalogo

Revision ID: 70ec94633e05
Revises: 35292009efa2
Create Date: 2026-09-20 15:03:06.132535

T017. `probe_items` y `/api/v1/_probe` existían solo para probar el aislamiento
entre empresas mientras 001 no tenía ninguna tabla de negocio real. Ese papel lo
cubre ahora `test_catalog_isolation.py` sobre `suppliers` y `products` (T011),
así que la sonda se retira, como 001 dejó anotado en su código.

Generada con --autogenerate y revisada a mano: el `downgrade` recrea la tabla
con sus tres FK y sus dos índices, así que la migración es reversible.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "70ec94633e05"
down_revision: str | Sequence[str] | None = "35292009efa2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_probe_items_company_id"), table_name="probe_items")
    op.drop_index(op.f("ix_probe_items_disabled_at"), table_name="probe_items")
    op.drop_table("probe_items")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "probe_items",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("company_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("name", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "disabled_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column("disabled_by", sa.UUID(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name=op.f("probe_items_company_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("probe_items_created_by_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["disabled_by"], ["users.id"], name=op.f("probe_items_disabled_by_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("probe_items_pkey")),
    )
    op.create_index(
        op.f("ix_probe_items_disabled_at"), "probe_items", ["disabled_at"], unique=False
    )
    op.create_index(
        op.f("ix_probe_items_company_id"), "probe_items", ["company_id"], unique=False
    )
