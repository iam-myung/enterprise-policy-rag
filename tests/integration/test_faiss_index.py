"""Step 6-RED：FAISS 索引集成测试（SPEC §5.314 / §9.2 / §10.1）。

验收点：
② FAISS 索引 receipt 可复核；候选按距离有序。
③ 用固定问题命中 gold evidence 页（基线 top 5 纯向量）。

本文件使用确定性 fake embedder（bag-of-chars），不调用真实 Embedding/网络。
RED 阶段 `adapters/retrieval/faiss_index.py` 尚未实现，`FaissIndex` 导入应失败。
"""

import hashlib

from enterprise_policy_rag.adapters.retrieval.faiss_index import FaissIndex
from enterprise_policy_rag.domain.entities import KnowledgeChunk


def _chunk(chunk_id: str, doc_id: str, ordinal: int, text: str) -> KnowledgeChunk:
    """构造最小合法 KnowledgeChunk（text == 源文本区间，不跨页）。"""
    return KnowledgeChunk(
        id=chunk_id,
        document_id=doc_id,
        ordinal=ordinal,
        page=1,
        char_start=0,
        char_end=len(text),
        text=text,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        token_count=max(1, len(text)),
    )


# 确定性 fake embedder：按字符 bag-of-chars 映射为固定维度向量。
_VOCAB = list("年假每十五天有少出差报销标准流程员工加制度")


def _embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for t in texts:
        vec = [0.0] * len(_VOCAB)
        for ch in t:
            if ch in _VOCAB:
                vec[_VOCAB.index(ch)] += 1.0
        out.append(vec)
    return out


def _manifest_sha256(chunks: tuple[KnowledgeChunk, ...]) -> str:
    """契约：receipt 的 manifest_sha256 必须等于对 chunks 规范化清单的 sha256。"""
    ordered = sorted(chunks, key=lambda c: (c.document_id, c.ordinal))
    payload = "\n".join(
        f"{c.document_id}:{c.ordinal}:{c.text_sha256}" for c in ordered
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_faiss_receipt_auditable() -> None:
    """② receipt 可复核：revision/chunk_count 正确，manifest_sha256 与清单一致。"""
    chunks = (
        _chunk("c1", "d1", 0, "年假每年十五天"),
        _chunk("c2", "d1", 1, "出差报销标准"),
    )
    idx = FaissIndex(embedder=_embed)
    receipt = idx.build(chunks, revision="rev1")
    assert receipt.revision == "rev1"
    assert receipt.chunk_count == 2
    assert receipt.manifest_sha256 == _manifest_sha256(chunks)


def test_faiss_candidates_ordered_by_distance() -> None:
    """② 候选按距离有序（距离升序，最近优先）。"""
    chunks = (
        _chunk("c1", "d1", 0, "年假每年十五天"),
        _chunk("c2", "d1", 1, "出差报销标准"),
        _chunk("c3", "d2", 0, "员工加班制度"),
    )
    idx = FaissIndex(embedder=_embed)
    idx.build(chunks, revision="rev1")
    candidates = idx.query("年假有多少天", revision="rev1", top_k=3)
    distances = [c.distance for c in candidates]
    assert distances == sorted(distances)


def test_faiss_revision_isolation() -> None:
    """① 索引按 corpus revision 隔离：查 rev 只返回该 rev 的 chunks。"""
    idx = FaissIndex(embedder=_embed)
    idx.build((_chunk("c1", "d1", 0, "年假每年十五天"),), revision="rev1")
    idx.build((_chunk("c2", "d2", 0, "员工加班制度"),), revision="rev2")

    rev1_hits = {c.chunk_id for c in idx.query("年假", revision="rev1", top_k=5)}
    rev2_hits = {c.chunk_id for c in idx.query("加班", revision="rev2", top_k=5)}

    assert rev1_hits == {"c1"}
    assert rev2_hits == {"c2"}


def test_fixed_question_hits_gold_page() -> None:
    """③ 固定问题命中 gold evidence 页（基线 top 5 纯向量）。"""
    chunks = (
        _chunk("c1", "d1", 0, "出差报销标准流程"),
        _chunk("c2", "d2", 0, "员工加班制度"),
        _chunk("gold", "d3", 0, "年假每年十五天"),
    )
    idx = FaissIndex(embedder=_embed)
    idx.build(chunks, revision="rev1")
    candidates = idx.query("年假有多少天", revision="rev1", top_k=5)
    assert "gold" in {c.chunk_id for c in candidates}
