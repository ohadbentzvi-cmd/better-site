"""admin: add is_superadmin column + seed initial superadmin

Adds ops.analysts.is_superadmin (boolean, default false). The first
superadmin is seeded from ADMIN_SUPERADMIN_USERNAME + ADMIN_SUPERADMIN_PASSWORD
env vars at migration time. If those vars are not set, the column is added
but no seed row is created — you can promote an existing analyst later via
a manual UPDATE.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-16

"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysts",
        sa.Column(
            "is_superadmin",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="ops",
    )

    username = os.environ.get("ADMIN_SUPERADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_SUPERADMIN_PASSWORD", "").strip()

    if username and password:
        from passlib.context import CryptContext

        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
        pw_hash = pwd_ctx.hash(password)

        op.execute(
            sa.text(
                """
                INSERT INTO ops.analysts (id, username, password_hash, active, is_superadmin, created_at, updated_at)
                VALUES (gen_random_uuid(), :username, :pw_hash, true, true, now(), now())
                ON CONFLICT (username) DO UPDATE SET is_superadmin = true
                """
            ).bindparams(username=username, pw_hash=pw_hash)
        )


def downgrade() -> None:
    op.drop_column("analysts", "is_superadmin", schema="ops")
