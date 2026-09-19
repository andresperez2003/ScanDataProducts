"""eliminar login_attempts: bloqueo por intentos fuera de alcance (D-4)

Revision ID: c24b02cadd6e
Revises: f15e1c85de6d
Create Date: 2026-09-19 14:03:28.564494

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c24b02cadd6e"
down_revision: str | Sequence[str] | None = "f15e1c85de6d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_login_attempts_attempted_at"), table_name="login_attempts")
    op.drop_index(
        op.f("ix_login_attempts_client_ip_attempted_at"), table_name="login_attempts"
    )
    op.drop_index(
        op.f("ix_login_attempts_username_attempted_at"), table_name="login_attempts"
    )
    op.drop_table("login_attempts")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "login_attempts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "username_normalized", sa.TEXT(), autoincrement=False, nullable=False
        ),
        sa.Column("client_ip", postgresql.INET(), autoincrement=False, nullable=False),
        sa.Column("succeeded", sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column(
            "attempted_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("login_attempts_pkey")),
    )
    op.create_index(
        op.f("ix_login_attempts_username_attempted_at"),
        "login_attempts",
        ["username_normalized", "attempted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_login_attempts_client_ip_attempted_at"),
        "login_attempts",
        ["client_ip", "attempted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_login_attempts_attempted_at"),
        "login_attempts",
        ["attempted_at"],
        unique=False,
    )
