"""Step 7-RED：SparseIndexPort 契约测试（SPEC §5.315）。

验收点：
① BM25 从当前 revision chunks 确定性重建（不用 pickle），中文分词命中制度编号/专有词。

本文件只测契约层（SparseIndexPort 协议 + SparseCandidate DTO 形状与不可变性），
行为层由 tests/integration/test_bm25_index.py 覆盖。
"""

from dataclasses import FrozenInstanceError

import pytest

from enterprise_policy_rag.application.ports.retrieval import (
    SparseCandidate,
    SparseIndexPort,
)


def test_sparse_candidate_fields() -> None:
    """SparseCandidate 字段：chunk_id / document_id / score（BM25 分数，越大越相关）。"""
    cand = SparseCandidate(chunk_id="c1", document_id="d1", score=3.5)
    assert cand.chunk_id == "c1"
    assert cand.document_id == "d1"
    assert cand.score == 3.5


def test_sparse_candidate_is_immutable() -> None:
    """候选快照不可变。"""
    cand = SparseCandidate("c1", "d1", 3.5)
    with pytest.raises(FrozenInstanceError):
        cand.score = 4.0  # type: ignore[misc]


def test_sparse_index_port_declares_build_and_query() -> None:
    """SparseIndexPort 协议必须声明 build / query 两个方法（SPEC §5.315）。"""
    assert hasattr(SparseIndexPort, "build")
    assert hasattr(SparseIndexPort, "query")
