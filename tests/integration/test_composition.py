"""composition 装配层集成测试。

回归守护：
① HybridIndex.build 返回 "<dir>/<revision>"，末段为 revision（而非字面量 "index"）。
② 连续 build（累积完整语料）后 retrieve 能命中多份文档。
"""

import hashlib

from enterprise_policy_rag.adapters.retrieval.bm25_index import BM25Index
from enterprise_policy_rag.adapters.retrieval.faiss_index import FaissIndex
from enterprise_policy_rag.composition import HybridIndex
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


# 确定性 fake embedder：bag-of-chars 映射为固定维度向量（不调用网络）。
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


class _NoneDocRepo:
    """retrieve 只调用 get(document_id)，返回 None 即可构造 Evidence。"""

    def get(self, document_id: str) -> None:  # noqa: ARG002
        return None


def test_hybrid_index_build_returns_index_relpath() -> None:
    """① build 返回 "<dir>/<revision>"，末段是 revision（非字面量 'index'）。"""
    hybrid = HybridIndex(FaissIndex(_embed), BM25Index())
    relpath = hybrid.build((_chunk("c1", "d1", 0, "年假每年十五天"),), "rev1")
    assert relpath == "index/rev1"
    assert relpath.rsplit("/", 1)[-1] == "rev1"


def test_hybrid_index_retrieve_covers_multiple_docs() -> None:
    """② 连续 build（累积完整语料）后 retrieve 能命中多份文档。"""
    hybrid = HybridIndex(FaissIndex(_embed), BM25Index())
    hybrid.build((_chunk("c1", "d1", 0, "年假每年十五天"),), "rev1")
    hybrid.build(
        (
            _chunk("c1", "d1", 0, "年假每年十五天"),
            _chunk("c2", "d2", 0, "员工加班制度"),
        ),
        "rev2",
    )
    evidence = hybrid.retrieve("年假有多少天", top_k=10, doc_repo=_NoneDocRepo())
    assert {e.chunk_id for e in evidence} == {"c1", "c2"}
