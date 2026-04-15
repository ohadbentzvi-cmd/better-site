"""leads: add state + source_metadata + email_source

Phase 2 Lead Generator prep:
    state           — ISO 3166-2 subdivision (e.g. "TX"). Needed for BBB URL
                      construction and scanner/sales-agent personalization.
    source_metadata — source-specific JSONB payload (bbb_rating,
                      bbb_profile_url, accredited, duplicate_listings, …).
    email_source    — audit trail for where the email came from
                      (bbb / extracted / fallback_info_at / NULL).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-15

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("state", sa.String(8), nullable=True), schema="ops")
    op.add_column(
        "leads",
        sa.Column(
            "source_metadata",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="ops",
    )
    op.add_column(
        "leads",
        sa.Column("email_source", sa.String(32), nullable=True),
        schema="ops",
    )
    op.create_index("idx_leads_state", "leads", ["state"], schema="ops")


def downgrade() -> None:
    op.drop_index("idx_leads_state", table_name="leads", schema="ops")
    op.drop_column("leads", "email_source", schema="ops")
    op.drop_column("leads", "source_metadata", schema="ops")
    op.drop_column("leads", "state", schema="ops")
