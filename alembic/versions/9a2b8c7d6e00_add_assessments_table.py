"""Add assessments table for case scoring / risk assessment

Revision ID: 9a2b8c7d6e00
Revises: 11116d6eac66
Create Date: 2026-07-10 10:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "9a2b8c7d6e00"
down_revision: Union[str, Sequence[str], None] = "11116d6eac66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("claim_id", sa.Uuid(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("overall_strength", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("strengths", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("weaknesses", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("risk_level", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="medium"),
        sa.Column("recommendations", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("assessments")