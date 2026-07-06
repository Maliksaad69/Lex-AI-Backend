"""uuid_cases_and_documents

Revision ID: b3e526a81b7e
Revises: 401899bba0f0
Create Date: 2026-07-05 15:19:17.381686

Drops and recreates cases with UUID PK. Creates documents table.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = 'b3e526a81b7e'
down_revision: Union[str, Sequence[str], None] = '401899bba0f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create pgcrypto extension for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # 2. Drop old cases table (test data only — no FK issues since documents doesn't exist yet)
    op.drop_table("cases")

    # 3. Recreate cases with UUID PK
    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("case_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("claim_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("current_stage", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="draft"),
        sa.Column("plaintiff_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("plaintiff_counsel", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("defense_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("defense_counsel", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("court", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("county", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("trial_date", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("summary", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("analysis", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="Not started"),
        sa.Column("document_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cases_user_id"), "cases", ["user_id"])
    op.create_index(op.f("ix_cases_case_name"), "cases", ["case_name"])

    # 4. Create documents table with UUID PK + FK to cases
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("case_id", sa.Uuid(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("file_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text_preview", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("chunks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qdrant_document_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_user_id"), "documents", ["user_id"])
    op.create_index(op.f("ix_documents_case_id"), "documents", ["case_id"])
    op.create_index(op.f("ix_documents_filename"), "documents", ["filename"])
    op.create_index(op.f("ix_documents_qdrant_document_id"), "documents", ["qdrant_document_id"])


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("cases")
    # Recreate old-style cases table
    op.create_table(
        "cases",
        sa.Column("case_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("case_name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("case_id"),
    )