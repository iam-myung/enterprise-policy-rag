"""检索 Ports（SPEC §5.314 / §5.315）。

DenseIndexPort / SparseIndexPort：索引按 corpus revision 隔离；query 返回 candidates。
所有 Port 返回不可变 DTO（IndexReceipt / EvidenceCandidate / SparseCandidate）。
"""

from dataclasses import dataclass
from typing import Protocol

from enterprise_policy_rag.domain.entities import KnowledgeChunk


@dataclass(frozen=True)
class IndexReceipt:
    """索引构建 receipt（可复核，SPEC §5.314）。

    manifest_sha256：对 chunks 按 (document_id, ordinal) 排序后的
    "{document_id}:{ordinal}:{text_sha256}" 清单取 sha256，供外部复核。
    """

    revision: str
    index_relpath: str
    chunk_count: int
    manifest_sha256: str


@dataclass(frozen=True)
class EvidenceCandidate:
    """稠密检索候选（distance 为 L2 距离，越小越近）。"""

    chunk_id: str
    document_id: str
    distance: float


@dataclass(frozen=True)
class SparseCandidate:
    """稀疏检索候选（score 为 BM25 分数，越大越相关）。"""

    chunk_id: str
    document_id: str
    score: float


class DenseIndexPort(Protocol):
    """稠密检索 Port（SPEC §5.314）。"""

    def build(
        self, chunks: tuple[KnowledgeChunk, ...], revision: str
    ) -> IndexReceipt: ...

    def query(
        self, query_text: str, revision: str, top_k: int = 5
    ) -> tuple[EvidenceCandidate, ...]: ...


class SparseIndexPort(Protocol):
    """稀疏检索 Port（SPEC §5.315）。"""

    def build(
        self, chunks: tuple[KnowledgeChunk, ...], revision: str
    ) -> IndexReceipt: ...

    def query(
        self, query_text: str, revision: str, top_k: int = 5
    ) -> tuple[SparseCandidate, ...]: ...
