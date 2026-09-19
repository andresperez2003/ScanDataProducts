"""probe_items temporal para verificar aislamiento (T016)

Revision ID: f15e1c85de6d
Revises: dfc595fa9493
Create Date: 2026-09-19 12:45:44.205815

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f15e1c85de6d"
down_revision: str | Sequence[str] | None = "dfc595fa9493"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "probe_items",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["disabled_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_probe_items_company_id"), "probe_items", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_probe_items_disabled_at"), "probe_items", ["disabled_at"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_probe_items_disabled_at"), table_name="probe_items")
    op.drop_index(op.f("ix_probe_items_company_id"), table_name="probe_items")
    op.drop_table("probe_items")
