"""SPEC §7.1 七张表结构与约束契约测试（Step 3-RED）。

引用尚未实现的 sqlite_models，运行时应以 ImportError 失败。
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprise_policy_rag.adapters.persistence.sqlite_models import (
    Base,
    CorpusRevisionModel,
)

EXPECTED_TABLES = {
    "policy_documents",
    "knowledge_chunks",
    "parsed_pages",
    "corpus_revisions",
    "corpus_revision_documents",
    "ingestion_runs",
    "query_runs",
}


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return eng


def test_seven_tables_exist(engine):
    tables = set(inspect(engine).get_table_names())
    assert tables == EXPECTED_TABLES


def test_policy_documents_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("policy_documents")}
    assert {
        "id", "sha256", "title", "version", "effective_at", "expires_at",
        "scope", "source_kind", "status", "source_relpath", "page_count",
        "row_version", "created_at_utc", "updated_at_utc",
    } <= cols


def test_policy_documents_sha256_unique(engine):
    unique_cols = {
        col
        for u in inspect(engine).get_unique_constraints("policy_documents")
        for col in u["column_names"]
    }
    assert "sha256" in unique_cols


def test_knowledge_chunks_composite_unique(engine):
    unique_sets = {
        tuple(sorted(u["column_names"]))
        for u in inspect(engine).get_unique_constraints("knowledge_chunks")
    }
    assert ("corpus_revision", "document_id", "ordinal") in unique_sets


def test_parsed_pages_composite_pk(engine):
    pk = inspect(engine).get_pk_constraint("parsed_pages")
    assert set(pk["constrained_columns"]) == {"document_id", "page_number"}


def test_corpus_revisions_unique_active_partial_index(engine):
    """partial unique index：status='ACTIVE' 至多一行。"""
    with Session(engine) as session:
        session.add(
            CorpusRevisionModel(
                revision="r1", status="ACTIVE", index_relpath="x",
                manifest_sha256="y", created_at_utc=datetime(2024, 1, 1),
            )
        )
        session.commit()
        session.add(
            CorpusRevisionModel(
                revision="r2", status="ACTIVE", index_relpath="x",
                manifest_sha256="y", created_at_utc=datetime(2024, 1, 1),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        # 非 ACTIVE 可多行
        session.add(
            CorpusRevisionModel(
                revision="r3", status="RETIRED", index_relpath="x",
                manifest_sha256="y", created_at_utc=datetime(2024, 1, 1),
            )
        )
        session.add(
            CorpusRevisionModel(
                revision="r4", status="RETIRED", index_relpath="x",
                manifest_sha256="y", created_at_utc=datetime(2024, 1, 1),
            )
        )
        session.commit()
