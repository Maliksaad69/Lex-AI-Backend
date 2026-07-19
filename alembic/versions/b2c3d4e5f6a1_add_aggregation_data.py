"""Add aggregation_data JSONB column to simulations table.

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-07-19 23:35:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("simulations", sa.Column("aggregation_data", JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb")))

def downgrade() -> None:
    op.drop_column("simulations", "aggregation_data")