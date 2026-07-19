"""Add pool_spec and stimulus columns to simulations table

Revision ID: 7d8e9f0a1b2c
Revises: ce0ae45f556f
Create Date: 2026-07-19 20:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "7d8e9f0a1b2c"
down_revision: Union[str, None] = "ce0ae45f556f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add pool_spec JSONB column
    op.add_column(
        "simulations",
        sa.Column("pool_spec", JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")),
    )
    # Add stimulus TEXT column
    op.add_column(
        "simulations",
        sa.Column("stimulus", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("simulations", "stimulus")
    op.drop_column("simulations", "pool_spec")