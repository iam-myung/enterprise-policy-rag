"""Step 6-RED：DenseIndexPort 契约测试（SPEC §5.314）。

验收点：
① DenseIndexPort：索引按 corpus revision 隔离；query 返回 evidence candidates。
② FAISS 索引 receipt 可复核；候选按距离有序。

本文件只测契约层（Port 协议 + DTO 形状与不可变性），
行为层由 tests/integration/test_faiss_index.py 覆盖。
"""

from dataclasses import FrozenInstanceError

import pytest

from enterprise_policy_rag.application.ports.retrieval import (
    DenseIndexPort,
    EvidenceCandidate,
    IndexReceipt,
)


def test_index_receipt_fields_auditable() -> None:
    """IndexReceipt 字段：revision / index_relpath / chunk_count / manifest_sha256。"""
    receipt = IndexReceipt(
        revision="rev1",
        index_relpath="rev1/faiss.index",
        chunk_count=3,
        manifest_sha256="a" * 64,
    )
    assert receipt.revision == "rev1"
    assert receipt.index_relpath == "rev1/faiss.index"
    assert receipt.chunk_count == 3
    assert len(receipt.manifest_sha256) == 64


def test_index_receipt_is_immutable() -> None:
    """receipt 发布后不可变（SPEC §4.1 不可变快照语义）。"""
    receipt = IndexReceipt("rev1", "rev1/faiss.index", 3, "a" * 64)
    with pytest.raises(FrozenInstanceError):
        receipt.chunk_count = 4  # type: ignore[misc]


def test_evidence_candidate_fields() -> None:
    """EvidenceCandidate 字段：chunk_id / document_id / distance。"""
    cand = EvidenceCandidate(chunk_id="c1", document_id="d1", distance=0.5)
    assert cand.chunk_id == "c1"
    assert cand.document_id == "d1"
    assert cand.distance == 0.5


def test_evidence_candidate_is_immutable() -> None:
    """候选快照不可变。"""
    cand = EvidenceCandidate("c1", "d1", 0.5)
    with pytest.raises(FrozenInstanceError):
        cand.distance = 0.6  # type: ignore[misc]


def test_dense_index_port_declares_build_and_query() -> None:
    """DenseIndexPort 协议必须声明 build / query 两个方法（SPEC §5.314）。"""
    assert hasattr(DenseIndexPort, "build")
    assert hasattr(DenseIndexPort, "query")
