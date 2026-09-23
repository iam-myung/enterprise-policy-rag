"""SQLite / SQLAlchemy 模型（SPEC §7.1 七张表）。"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """声明式基类。"""


class PolicyDocumentModel(Base):
    __tablename__ = "policy_documents"

    id = Column(String, primary_key=True)
    sha256 = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    version = Column(String, nullable=False)
    effective_at = Column(Date, nullable=True)
    expires_at = Column(Date, nullable=True)
    scope = Column(String, nullable=False)
    source_kind = Column(String, nullable=False)
    status = Column(String, nullable=False)
    source_relpath = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)
    row_version = Column(Integer, nullable=False, default=1)
    created_at_utc = Column(DateTime, nullable=False)
    updated_at_utc = Column(DateTime, nullable=False)


class ParsedPageModel(Base):
    __tablename__ = "parsed_pages"

    document_id = Column(String, ForeignKey("policy_documents.id"), primary_key=True)
    page_number = Column(Integer, primary_key=True)
    source_text = Column(Text, nullable=False)
    source_text_sha256 = Column(String, nullable=False)


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "corpus_revision", "ordinal",
            name="uq_chunk_doc_revision_ordinal",
        ),
    )

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("policy_documents.id"), nullable=False)
    corpus_revision = Column(String, nullable=False)
    ordinal = Column(Integer, nullable=False)
    page = Column(Integer, nullable=False)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    text_sha256 = Column(String, nullable=False)
    token_count = Column(Integer, nullable=False)


class CorpusRevisionModel(Base):
    __tablename__ = "corpus_revisions"
    __table_args__ = (
        Index(
            "uq_active_revision",
            "status",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    revision = Column(String, primary_key=True)
    status = Column(String, nullable=False)
    index_relpath = Column(String, nullable=False)
    manifest_sha256 = Column(String, nullable=False)
    created_at_utc = Column(DateTime, nullable=False)
    activated_at_utc = Column(DateTime, nullable=True)


class CorpusRevisionDocumentModel(Base):
    __tablename__ = "corpus_revision_documents"

    revision = Column(String, ForeignKey("corpus_revisions.revision"), primary_key=True)
    document_id = Column(String, ForeignKey("policy_documents.id"), primary_key=True)


class IngestionRunModel(Base):
    __tablename__ = "ingestion_runs"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("policy_documents.id"), nullable=False)
    status = Column(String, nullable=False)
    target_revision = Column(String, nullable=False)
    error_code = Column(String, nullable=True)
    error_context_json = Column(Text, nullable=True)
    trace_id = Column(String, nullable=False)
    started_at_utc = Column(DateTime, nullable=False)
    finished_at_utc = Column(DateTime, nullable=True)


class QueryRunModel(Base):
    __tablename__ = "query_runs"

    id = Column(String, primary_key=True)
    question_sha256 = Column(String, nullable=False)
    question_preview = Column(Text, nullable=True)
    answer_status = Column(String, nullable=False)
    corpus_revision = Column(String, nullable=False)
    citation_ids_json = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=False)
    trace_id = Column(String, nullable=False)
    created_at_utc = Column(DateTime, nullable=False)
