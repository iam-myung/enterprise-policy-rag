"""Step 7-RED：BM25 稀疏索引集成测试（SPEC §5.315 / §10.1）。

验收点：
① BM25 从当前 revision chunks 确定性重建（不用 pickle），中文分词命中制度编号/专有词。

RED 阶段 `adapters/retrieval/bm25_index.py` 尚未实现，`BM25Index` 导入应失败。
"""

import hashlib

from enterprise_policy_rag.adapters.retrieval.bm25_index import BM25Index
from enterprise_policy_rag.domain.entities import KnowledgeChunk


def _chunk(chunk_id: str, doc_id: str, ordinal: int, text: str) -> KnowledgeChunk:
    """构造最小合法 KnowledgeChunk。"""
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


def test_bm25_deterministic_rebuild() -> None:
    """① 同输入 → 确定性重建 → 同 query 结果一致。"""
    chunks = (
        _chunk("c1", "d1", 0, "员工年假每年十五天"),
        _chunk("c2", "d1", 1, "差旅费报销标准"),
        _chunk("c3", "d2", 0, "员工加班制度"),
    )
    idx1 = BM25Index()
    idx1.build(chunks, revision="rev1")
    idx2 = BM25Index()
    idx2.build(chunks, revision="rev1")

    r1 = idx1.query("年假", revision="rev1", top_k=3)
    r2 = idx2.query("年假", revision="rev1", top_k=3)
    assert [(c.chunk_id, c.score) for c in r1] == [(c.chunk_id, c.score) for c in r2]


def test_bm25_hits_chinese_special_term() -> None:
    """① 中文分词命中专有词（年假）。"""
    chunks = (
        _chunk("c1", "d1", 0, "员工年假每年十五天"),
        _chunk("c2", "d1", 1, "差旅费报销标准"),
        _chunk("c3", "d2", 0, "员工加班制度"),
    )
    idx = BM25Index()
    idx.build(chunks, revision="rev1")
    candidates = idx.query("年假天数", revision="rev1", top_k=3)
    assert candidates, "应有候选"
    assert candidates[0].chunk_id == "c1"


def test_bm25_hits_regulation_number() -> None:
    """① 中文分词命中制度编号（第一条）。"""
    chunks = (
        _chunk("c1", "d1", 0, "第一条：员工年假每年十五天"),
        _chunk("c2", "d1", 1, "第二条：差旅费报销标准"),
    )
    idx = BM25Index()
    idx.build(chunks, revision="rev1")
    candidates = idx.query("第一条", revision="rev1", top_k=2)
    assert candidates, "应有候选"
    assert candidates[0].chunk_id == "c1"


def test_bm25_revision_isolation() -> None:
    """① 索引按 corpus revision 隔离。"""
    idx = BM25Index()
    idx.build((_chunk("c1", "d1", 0, "员工年假每年十五天"),), revision="rev1")
    idx.build((_chunk("c2", "d2", 0, "员工加班制度"),), revision="rev2")

    assert {c.chunk_id for c in idx.query("年假", revision="rev1", top_k=5)} == {"c1"}
    assert {c.chunk_id for c in idx.query("加班", revision="rev2", top_k=5)} == {"c2"}
