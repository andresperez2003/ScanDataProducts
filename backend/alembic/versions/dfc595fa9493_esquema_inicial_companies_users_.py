"""esquema inicial: companies, users, sessions, login_attempts

Revision ID: dfc595fa9493
Revises:
Create Date: 2026-09-19 10:26:20.196779

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dfc595fa9493"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "companies",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_normalized", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name_normalized"),
    )
    op.create_index(
        op.f("ix_companies_disabled_at"), "companies", ["disabled_at"], unique=False
    )
    op.create_table(
        "login_attempts",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("username_normalized", sa.Text(), nullable=False),
        sa.Column("client_ip", postgresql.INET(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_login_attempts_attempted_at"),
        "login_attempts",
        ["attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_login_attempts_client_ip_attempted_at",
        "login_attempts",
        ["client_ip", "attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_login_attempts_username_attempted_at",
        "login_attempts",
        ["username_normalized", "attempted_at"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("username_normalized", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["disabled_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username_normalized"),
    )
    op.create_index(op.f("ix_users_company_id"), "users", ["company_id"], unique=False)
    op.create_index(
        op.f("ix_users_disabled_at"), "users", ["disabled_at"], unique=False
    )
    # Revisado a mano: FK circular companies.disabled_by -> users.id. Se añade
    # después de crear users y es diferida (plan §4, Notas de esquema).
    op.create_foreign_key(
        "fk_companies_disabled_by_users",
        "companies",
        "users",
        ["disabled_by"],
        ["id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "sessions",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_sessions_token_hash_active",
        "sessions",
        ["token_hash"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(
        "ix_sessions_token_hash_active",
        table_name="sessions",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_table("sessions")
    op.drop_constraint(
        "fk_companies_disabled_by_users", "companies", type_="foreignkey"
    )
    op.drop_index(op.f("ix_users_disabled_at"), table_name="users")
    op.drop_index(op.f("ix_users_company_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(
        "ix_login_attempts_username_attempted_at", table_name="login_attempts"
    )
    op.drop_index(
        "ix_login_attempts_client_ip_attempted_at", table_name="login_attempts"
    )
    op.drop_index(op.f("ix_login_attempts_attempted_at"), table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_index(op.f("ix_companies_disabled_at"), table_name="companies")
    op.drop_table("companies")
