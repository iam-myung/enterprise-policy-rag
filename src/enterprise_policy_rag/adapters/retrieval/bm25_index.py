"""BM25 稀疏索引适配器（SPEC §5.315 / §10.1）。

实现 SparseIndexPort：从当前 revision chunks 确定性重建（内存重建，不用 pickle），
中文分词（jieba）命中制度编号/专有词。

采用自定义 BM25（平滑 IDF：idf = log(1 + (N-df+0.5)/(df+0.5))），
保证小文档集下 idf 非负、排序稳定（避免 rank_bm25 在 df≈N 时 idf≤0 的退化）。
"""

import hashlib
import math
from collections.abc import Callable

from enterprise_policy_rag.application.ports.retrieval import (
    IndexReceipt,
    SparseCandidate,
)
from enterprise_policy_rag.domain.entities import KnowledgeChunk


class _BM25:
    """确定性 BM25（BM25Okapi 打分 + 平滑 IDF）。"""

    def __init__(
        self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75
    ) -> None:
        self._k1 = k1
        self._b = b
        self._n = len(corpus)
        self._avgdl = sum(len(doc) for doc in corpus) / max(1, self._n)
        self._doc_len = [len(doc) for doc in corpus]
        self._doc_freq: dict[str, int] = {}
        self._term_freq: list[dict[str, int]] = []
        for doc in corpus:
            tf: dict[str, int] = {}
            for term in doc:
                tf[term] = tf.get(term, 0) + 1
            self._term_freq.append(tf)
            for term in tf:
                self._doc_freq[term] = self._doc_freq.get(term, 0) + 1

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def scores(self, query_tokens: list[str]) -> list[float]:
        result: list[float] = []
        for i in range(self._n):
            doc_len = self._doc_len[i]
            tf = self._term_freq[i]
            score = 0.0
            for term in query_tokens:
                freq = tf.get(term)
                if freq is None:
                    continue
                idf = self._idf(term)
                denom = freq + self._k1 * (
                    1 - self._b + self._b * doc_len / max(1, self._avgdl)
                )
                score += idf * freq * (self._k1 + 1) / denom
            result.append(score)
        return result


class BM25Index:
    """BM25 稀疏索引（jieba 分词 + 平滑 IDF BM25）。

    tokenizer 可注入（默认 jieba.lcut）；索引以 revision 为键在内存隔离，
    不反序列化 pickle，同输入确定性重建。
    """

    def __init__(
        self, tokenizer: Callable[[str], list[str]] | None = None
    ) -> None:
        import jieba  # type: ignore[import-untyped]

        self._tokenizer = tokenizer or jieba.lcut
        self._indexes: dict[str, _BM25] = {}
        self._chunks: dict[str, tuple[KnowledgeChunk, ...]] = {}

    def build(
        self, chunks: tuple[KnowledgeChunk, ...], revision: str
    ) -> IndexReceipt:
        tokenized = [self._tokenizer(c.text) for c in chunks]
        self._indexes[revision] = _BM25(tokenized)
        self._chunks[revision] = tuple(chunks)

        return IndexReceipt(
            revision=revision,
            index_relpath=f"{revision}/bm25",
            chunk_count=len(chunks),
            manifest_sha256=self._manifest_sha256(chunks),
        )

    def query(
        self, query_text: str, revision: str, top_k: int = 5
    ) -> tuple[SparseCandidate, ...]:
        index = self._indexes[revision]
        chunks = self._chunks[revision]
        scores = index.scores(self._tokenizer(query_text))

        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        candidates: list[SparseCandidate] = []
        for pos, score in ranked[:top_k]:
            if score <= 0.0:  # 无匹配的 chunk 不返回
                continue
            chunk = chunks[pos]
            candidates.append(
                SparseCandidate(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    score=float(score),
                )
            )
        return tuple(candidates)

    @staticmethod
    def _manifest_sha256(chunks: tuple[KnowledgeChunk, ...]) -> str:
        ordered = sorted(chunks, key=lambda c: (c.document_id, c.ordinal))
        payload = "\n".join(
            f"{c.document_id}:{c.ordinal}:{c.text_sha256}" for c in ordered
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
