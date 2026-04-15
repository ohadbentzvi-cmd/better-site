"""scans: scoring columns + raw metrics + partial-scan flag

Phase 2.5 Scanner prep:
    score_performance / score_seo / score_ai_readiness / score_security
        — per-dimension scores (0-100), NULL when that dimension was
          unmeasurable (e.g. PageSpeed API timed out).
    raw_metrics      — JSONB with LCP/CLS/TBT/FCP/TTFB/page_weight/etc.
    scanned_url      — the canonical URL actually scanned (may differ from
                       lead.website_url if redirects happened).
    pagespeed_available — False when PageSpeed API failed for this scan.
    scan_partial     — True when at least one dimension was unmeasurable;
                       overall_score is also NULL when this is True.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-15

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("score_performance", sa.Integer, nullable=True), schema="ops")
    op.add_column("scans", sa.Column("score_seo", sa.Integer, nullable=True), schema="ops")
    op.add_column("scans", sa.Column("score_ai_readiness", sa.Integer, nullable=True), schema="ops")
    op.add_column("scans", sa.Column("score_security", sa.Integer, nullable=True), schema="ops")
    op.add_column(
        "scans",
        sa.Column(
            "raw_metrics",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="ops",
    )
    op.add_column("scans", sa.Column("scanned_url", sa.String(1024), nullable=True), schema="ops")
    op.add_column(
        "scans",
        sa.Column(
            "pagespeed_available",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        schema="ops",
    )
    op.add_column(
        "scans",
        sa.Column(
            "scan_partial",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="ops",
    )
    # When a scan is partial, overall score is NULL. Allow it.
    op.alter_column("scans", "score", nullable=True, schema="ops")


def downgrade() -> None:
    op.alter_column("scans", "score", nullable=False, schema="ops")
    op.drop_column("scans", "scan_partial", schema="ops")
    op.drop_column("scans", "pagespeed_available", schema="ops")
    op.drop_column("scans", "scanned_url", schema="ops")
    op.drop_column("scans", "raw_metrics", schema="ops")
    op.drop_column("scans", "score_security", schema="ops")
    op.drop_column("scans", "score_ai_readiness", schema="ops")
    op.drop_column("scans", "score_seo", schema="ops")
    op.drop_column("scans", "score_performance", schema="ops")
