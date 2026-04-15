"""admin: analysts, login_attempts, lead_reviews, scan_reviews

Introduces the Admin Review Console tables:
    ops.analysts          — named reviewers with bcrypt password_hash
    ops.login_attempts    — rate-limit + audit log for /auth/verify
    ops.lead_reviews      — append-only approve/reject + reason + note
    ops.scan_reviews      — append-only free-text feedback on scan scores

All writes are append-only (no UPDATE, no DELETE in normal flow). Invariants
are enforced by Postgres CHECK constraints, not app-layer only.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-16

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


LEAD_REVIEW_VERDICT = postgresql.ENUM(
    "approved",
    "rejected",
    name="lead_review_verdict",
    schema="ops",
    create_type=False,
)
LEAD_REVIEW_REASON = postgresql.ENUM(
    "not_icp",
    "site_already_good",
    "site_broken_or_dead",
    "duplicate_or_other",
    name="lead_review_reason",
    schema="ops",
    create_type=False,
)


def upgrade() -> None:
    # Enums first — referenced by lead_reviews.
    op.execute(
        "CREATE TYPE ops.lead_review_verdict AS ENUM ('approved', 'rejected')"
    )
    op.execute(
        "CREATE TYPE ops.lead_review_reason AS ENUM ("
        "'not_icp', 'site_already_good', 'site_broken_or_dead', 'duplicate_or_other'"
        ")"
    )

    op.create_table(
        "analysts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "active", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="ops",
    )

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column(
            "attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="ops",
    )
    op.create_index(
        "idx_login_attempts_username_time",
        "login_attempts",
        ["username", "attempt_at"],
        schema="ops",
    )

    op.create_table(
        "lead_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ops.leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analyst_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ops.analysts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("verdict", LEAD_REVIEW_VERDICT, nullable=False),
        sa.Column("reason_code", LEAD_REVIEW_REASON, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "(verdict = 'approved' AND reason_code IS NULL) "
            "OR (verdict = 'rejected' "
            "    AND reason_code IS NOT NULL "
            "    AND (reason_code <> 'duplicate_or_other' "
            "         OR (note IS NOT NULL AND length(btrim(note)) > 0)))",
            name="lead_review_verdict_shape",
        ),
        schema="ops",
    )
    op.create_index(
        "idx_lead_reviews_lead_id_created",
        "lead_reviews",
        ["lead_id", "created_at"],
        schema="ops",
    )

    op.create_table(
        "scan_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ops.scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analyst_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ops.analysts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reasoning", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "length(btrim(reasoning)) > 0",
            name="scan_review_reasoning_nonempty",
        ),
        schema="ops",
    )
    op.create_index(
        "idx_scan_reviews_scan_id_created",
        "scan_reviews",
        ["scan_id", "created_at"],
        schema="ops",
    )


def downgrade() -> None:
    op.drop_index("idx_scan_reviews_scan_id_created", "scan_reviews", schema="ops")
    op.drop_table("scan_reviews", schema="ops")
    op.drop_index("idx_lead_reviews_lead_id_created", "lead_reviews", schema="ops")
    op.drop_table("lead_reviews", schema="ops")
    op.drop_index("idx_login_attempts_username_time", "login_attempts", schema="ops")
    op.drop_table("login_attempts", schema="ops")
    op.drop_table("analysts", schema="ops")
    op.execute("DROP TYPE ops.lead_review_reason")
    op.execute("DROP TYPE ops.lead_review_verdict")
