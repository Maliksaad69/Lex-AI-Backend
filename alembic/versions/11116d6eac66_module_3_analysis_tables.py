"""module 3 analysis tables

Creates: extracted_facts, parties, claims, evidence_links,
         timeline_events, contradictions

Revision ID: 11116d6eac66
Revises: 54c5de3c5769
Create Date: 2026-07-07 19:45:31.753237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '11116d6eac66'
down_revision: Union[str, Sequence[str], None] = '54c5de3c5769'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── extracted_facts ────────────────────────────────────────────
    op.create_table(
        "extracted_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("statement", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source_document", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("page_number", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("importance_score", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_disputed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ai_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("human_reviewed", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── parties ─────────────────────────────────────────────────────
    op.create_table(
        "parties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── claims ──────────────────────────────────────────────────────
    op.create_table(
        "claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("claim_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("legal_basis", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("elements", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── evidence_links ──────────────────────────────────────────────
    op.create_table(
        "evidence_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("fact_id", sa.Uuid(), sa.ForeignKey("extracted_facts.id"), nullable=False),
        sa.Column("relationship", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("weight_score", sa.Integer(), nullable=False),
        sa.Column("rationale", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── timeline_events ─────────────────────────────────────────────
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("event_date", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("significance", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── contradictions ──────────────────────────────────────────────
    op.create_table(
        "contradictions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("fact_a_id", sa.Uuid(), sa.ForeignKey("extracted_facts.id"), nullable=False),
        sa.Column("fact_b_id", sa.Uuid(), sa.ForeignKey("extracted_facts.id"), nullable=False),
        sa.Column("nature", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("impact", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("contradictions")
    op.drop_table("timeline_events")
    op.drop_table("evidence_links")
    op.drop_table("claims")
    op.drop_table("parties")
    op.drop_table("extracted_facts")