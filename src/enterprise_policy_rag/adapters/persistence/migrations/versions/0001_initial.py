"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("sha256", sa.String(), nullable=False, unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("effective_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source_relpath", sa.String(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at_utc", sa.DateTime(), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "parsed_pages",
        sa.Column(
            "document_id",
            sa.String(),
            sa.ForeignKey("policy_documents.id"),
            primary_key=True,
        ),
        sa.Column("page_number", sa.Integer(), primary_key=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_text_sha256", sa.String(), nullable=False),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("policy_documents.id"), nullable=False),
        sa.Column("corpus_revision", sa.String(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "document_id",
            "corpus_revision",
            "ordinal",
            name="uq_chunk_doc_revision_ordinal",
        ),
    )
    op.create_table(
        "corpus_revisions",
        sa.Column("revision", sa.String(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("index_relpath", sa.String(), nullable=False),
        sa.Column("manifest_sha256", sa.String(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(), nullable=False),
        sa.Column("activated_at_utc", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_active_revision",
        "corpus_revisions",
        ["status"],
        unique=True,
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "corpus_revision_documents",
        sa.Column(
            "revision",
            sa.String(),
            sa.ForeignKey("corpus_revisions.revision"),
            primary_key=True,
        ),
        sa.Column(
            "document_id",
            sa.String(),
            sa.ForeignKey("policy_documents.id"),
            primary_key=True,
        ),
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_id", sa.String(), sa.ForeignKey("policy_documents.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("target_revision", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_context_json", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("started_at_utc", sa.DateTime(), nullable=False),
        sa.Column("finished_at_utc", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "query_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("question_sha256", sa.String(), nullable=False),
        sa.Column("question_preview", sa.Text(), nullable=True),
        sa.Column("answer_status", sa.String(), nullable=False),
        sa.Column("corpus_revision", sa.String(), nullable=False),
        sa.Column("citation_ids_json", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("query_runs")
    op.drop_table("ingestion_runs")
    op.drop_table("corpus_revision_documents")
    op.drop_index("uq_active_revision", table_name="corpus_revisions")
    op.drop_table("corpus_revisions")
    op.drop_table("knowledge_chunks")
    op.drop_table("parsed_pages")
    op.drop_table("policy_documents")
