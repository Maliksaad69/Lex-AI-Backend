"""Add name, biography columns to personas table, rename personality to behavioral_profile

Revision ID: a1b2c3d4e5f6
Revises: 7d8e9f0a1b2c
Create Date: 2026-07-19 21:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7d8e9f0a1b2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add name column
    op.add_column("personas", sa.Column("name", sa.String(), nullable=True))
    # Add biography column
    op.add_column("personas", sa.Column("biography", sa.Text(), nullable=True))
    # Rename personality -> behavioral_profile (JSONB)
    op.alter_column("personas", "personality", new_column_name="behavioral_profile")


def downgrade() -> None:
    op.alter_column("personas", "behavioral_profile", new_column_name="personality")
    op.drop_column("personas", "biography")
    op.drop_column("personas", "name")