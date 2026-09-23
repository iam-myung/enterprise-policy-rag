"""KnowledgeChunk 不变量测试（SPEC §4.1）。

Step 2-RED：引用尚未实现的 KnowledgeChunk / validate_chunk_source / validate_chunk_ordinals，
运行时应以 ImportError 失败。
"""

import pytest

from enterprise_policy_rag.domain.entities import KnowledgeChunk
from enterprise_policy_rag.domain.policy_rules import (
    validate_chunk_ordinals,
    validate_chunk_source,
)

SOURCE = "第一条：员工应按时上下班。第二条：请假需提前申请。"


def _chunk(**overrides):
    kwargs = dict(
        id="c1",
        document_id="doc-1",
        ordinal=1,
        page=1,
        char_start=0,
        char_end=10,
        text=SOURCE[0:10],
        text_sha256="x",
        token_count=5,
    )
    kwargs.update(overrides)
    return KnowledgeChunk(**kwargs)


def test_chunk_text_matches_source_slice():
    chunk = _chunk()
    validate_chunk_source(chunk, SOURCE)  # 不抛异常


def test_chunk_text_mismatch_rejected():
    chunk = _chunk(text="错误文本")
    with pytest.raises(ValueError):
        validate_chunk_source(chunk, SOURCE)


def test_chunk_full_page_slice_accepted():
    chunk = _chunk(char_start=0, char_end=len(SOURCE), text=SOURCE)
    validate_chunk_source(chunk, SOURCE)


def test_chunk_char_end_out_of_range_rejected():
    chunk = _chunk(char_end=len(SOURCE) + 100, text=SOURCE + "x" * 100)
    with pytest.raises(ValueError):
        validate_chunk_source(chunk, SOURCE)


def test_duplicate_ordinal_same_document_rejected():
    c1 = _chunk(id="c1", ordinal=1)
    c2 = _chunk(id="c2", ordinal=1)
    with pytest.raises(ValueError):
        validate_chunk_ordinals([c1, c2])


def test_unique_ordinal_accepted():
    c1 = _chunk(id="c1", ordinal=1)
    c2 = _chunk(id="c2", ordinal=2)
    validate_chunk_ordinals([c1, c2])


def test_ordinal_duplicate_across_documents_allowed():
    c1 = _chunk(id="c1", document_id="doc-1", ordinal=1)
    c2 = _chunk(id="c2", document_id="doc-2", ordinal=1)
    validate_chunk_ordinals([c1, c2])
