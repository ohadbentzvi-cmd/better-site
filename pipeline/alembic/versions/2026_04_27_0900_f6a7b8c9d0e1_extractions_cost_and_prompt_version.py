"""extractions: add cost_usd + prompt_version columns

Phase 3 Information Extractor prep:
    cost_usd        — USD cost summed across LLM calls for this row.
                      Source-of-truth for the per-batch cost ceiling
                      (see CLAUDE_COST_CEILING_PER_BATCH_USD).
                      0.0 for purely deterministic strategies.
    prompt_version  — version tag of the prompt that produced this row;
                      lets us filter for prompt iteration without
                      re-running a whole batch.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-27

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "extractions",
        sa.Column(
            "cost_usd",
            sa.Float,
            nullable=False,
            server_default=sa.text("0.0"),
        ),
        schema="ops",
    )
    op.add_column(
        "extractions",
        sa.Column("prompt_version", sa.String(64), nullable=True),
        schema="ops",
    )


def downgrade() -> None:
    op.drop_column("extractions", "prompt_version", schema="ops")
    op.drop_column("extractions", "cost_usd", schema="ops")
