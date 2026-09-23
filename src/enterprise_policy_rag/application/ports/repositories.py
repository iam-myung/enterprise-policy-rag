"""持久化 Ports（SPEC §5）。"""

from typing import Protocol

from enterprise_policy_rag.domain.entities import (
    CorpusSnapshot,
    KnowledgeChunk,
    ParsedPage,
    PolicyDocument,
)


class CorpusRevisionRepositoryPort(Protocol):
    """语料 revision 仓储：原子切换 active revision，任一时刻唯一 ACTIVE。"""

    def activate(
        self,
        revision: str,
        index_relpath: str,
        manifest_sha256: str,
        document_ids: list[str],
    ) -> None: ...

    def get_active(self) -> CorpusSnapshot | None: ...


class DocumentRepositoryPort(Protocol):
    """文档仓储：文档实体/查询条件 → 不可变文档快照。"""

    def add(self, document: PolicyDocument) -> None: ...

    def get(self, document_id: str) -> PolicyDocument | None: ...

    def get_by_sha256(self, sha256: str) -> PolicyDocument | None: ...

    def add_parsed_pages(self, pages: tuple[ParsedPage, ...]) -> None: ...

    def add_chunks(
        self, chunks: tuple[KnowledgeChunk, ...], revision: str
    ) -> None: ...

    def list_chunks_by_documents(
        self, document_ids: list[str]
    ) -> tuple[KnowledgeChunk, ...]: ...
