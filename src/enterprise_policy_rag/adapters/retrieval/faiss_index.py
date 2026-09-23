"""FAISS 稠密索引适配器（SPEC §5.314 / §10.1）。

实现 DenseIndexPort：索引按 corpus revision 隔离；候选按 L2 距离升序；
禁止反序列化不可信 pickle（仅内存构建，绝不 load/read pickle）。
"""

import hashlib
from collections.abc import Callable

import faiss
import numpy as np

from enterprise_policy_rag.application.ports.retrieval import (
    EvidenceCandidate,
    IndexReceipt,
)
from enterprise_policy_rag.domain.entities import KnowledgeChunk


class FaissIndex:
    """FAISS IndexFlatL2 稠密索引。

    embedder 为可调用对象：embedder(texts: list[str]) -> list[list[float]]。
    索引以 revision 为键在内存隔离；index_relpath 按 revision 命名，不写磁盘。
    """

    def __init__(
        self, embedder: Callable[[list[str]], list[list[float]]]
    ) -> None:
        self._embedder = embedder
        self._indexes: dict[str, faiss.IndexFlatL2] = {}
        self._chunks: dict[str, tuple[KnowledgeChunk, ...]] = {}

    def build(
        self, chunks: tuple[KnowledgeChunk, ...], revision: str
    ) -> IndexReceipt:
        matrix = np.asarray(
            self._embedder([c.text for c in chunks]), dtype="float32"
        )
        dim = matrix.shape[1]
        index = faiss.IndexFlatL2(dim)
        index.add(matrix)

        self._indexes[revision] = index
        self._chunks[revision] = tuple(chunks)

        return IndexReceipt(
            revision=revision,
            index_relpath=f"{revision}/faiss.index",
            chunk_count=len(chunks),
            manifest_sha256=self._manifest_sha256(chunks),
        )

    def query(
        self, query_text: str, revision: str, top_k: int = 5
    ) -> tuple[EvidenceCandidate, ...]:
        index = self._indexes[revision]
        chunks = self._chunks[revision]
        query_vec = np.asarray(self._embedder([query_text]), dtype="float32")

        k = min(top_k, len(chunks))
        distances, ids = index.search(query_vec, k)

        candidates: list[EvidenceCandidate] = []
        for distance, chunk_pos in zip(distances[0], ids[0], strict=True):
            if chunk_pos < 0:  # 过滤 FAISS 在不足 top_k 时返回的 -1
                continue
            chunk = chunks[int(chunk_pos)]
            candidates.append(
                EvidenceCandidate(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    distance=float(distance),
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
