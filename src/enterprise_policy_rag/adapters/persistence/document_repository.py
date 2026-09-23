"""持久化仓储实现（SPEC §2.2 adapters.persistence）。

只有 Repository Adapter 访问 SQLite；业务规则不入适配器。
"""

import io
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from pypdf import PdfReader, PdfWriter
from sqlalchemy.orm import Session

from enterprise_policy_rag.adapters.persistence.sqlite_models import (
    CorpusRevisionDocumentModel,
    CorpusRevisionModel,
    KnowledgeChunkModel,
    ParsedPageModel,
    PolicyDocumentModel,
)
from enterprise_policy_rag.application.contracts.documents import DocumentSummaryDTO
from enterprise_policy_rag.domain.entities import (
    CorpusSnapshot,
    DocumentStatus,
    KnowledgeChunk,
    ParsedPage,
    PolicyDocument,
)
from enterprise_policy_rag.domain.errors import (
    DocumentNotFoundError,
    DocumentNotReadyError,
    PageOutOfRangeError,
)


class CorpusRevisionRepository:
    """CorpusRevisionRepositoryPort 的 SQLite 实现（SPEC §5）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def activate(
        self,
        revision: str,
        index_relpath: str,
        manifest_sha256: str,
        document_ids: list[str],
    ) -> None:
        """原子切换 active revision：旧 ACTIVE 变 RETIRED，新 revision 变 ACTIVE。"""
        now = datetime.now(UTC).replace(tzinfo=None)
        self._session.query(CorpusRevisionModel).filter(
            CorpusRevisionModel.status == "ACTIVE"
        ).update({"status": "RETIRED", "activated_at_utc": None})
        self._session.add(
            CorpusRevisionModel(
                revision=revision,
                status="ACTIVE",
                index_relpath=index_relpath,
                manifest_sha256=manifest_sha256,
                created_at_utc=now,
                activated_at_utc=now,
            )
        )
        for doc_id in document_ids:
            self._session.add(
                CorpusRevisionDocumentModel(revision=revision, document_id=doc_id)
            )
        self._session.commit()

    def get_active(self) -> CorpusSnapshot | None:
        """返回当前 ACTIVE revision 的不可变快照；无则返回 None。"""
        row = (
            self._session.query(CorpusRevisionModel)
            .filter(CorpusRevisionModel.status == "ACTIVE")
            .one_or_none()
        )
        if row is None:
            return None
        doc_ids = tuple(
            str(r.document_id)
            for r in self._session.query(CorpusRevisionDocumentModel)
            .filter(CorpusRevisionDocumentModel.revision == row.revision)
            .order_by(CorpusRevisionDocumentModel.document_id)
        )
        return CorpusSnapshot(
            revision=str(row.revision),
            active_document_ids=doc_ids,
            index_path=str(row.index_relpath),
            created_at=cast(datetime, row.created_at_utc),
        )


class DocumentRepository:
    """DocumentRepositoryPort 的 SQLite 实现 + 文档查询（SPEC §5 / §8.4 / §8.6）。"""

    def __init__(self, session: Session, workspace_root: Path) -> None:
        self._session = session
        self._workspace_root = workspace_root

    def add(self, document: PolicyDocument) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        model = PolicyDocumentModel(
            id=document.id,
            sha256=document.sha256,
            title=document.title,
            version=document.version,
            effective_at=document.effective_at,
            expires_at=document.expires_at,
            scope=document.scope,
            source_kind=document.source_kind,
            status=document.status.value,
            source_relpath=document.source_relpath,
            page_count=document.page_count,
            created_at_utc=now,
            updated_at_utc=now,
        )
        self._session.add(model)
        self._session.commit()

    def add_parsed_pages(self, pages: tuple[ParsedPage, ...]) -> None:
        """保存规范页文本（SPEC §7.1 parsed_pages）。"""
        for page in pages:
            self._session.add(
                ParsedPageModel(
                    document_id=page.document_id,
                    page_number=page.page_number,
                    source_text=page.source_text,
                    source_text_sha256=page.source_text_sha256,
                )
            )
        self._session.commit()

    def add_chunks(
        self, chunks: tuple[KnowledgeChunk, ...], revision: str
    ) -> None:
        """保存知识切片（SPEC §7.1 knowledge_chunks），绑定 corpus_revision。"""
        for chunk in chunks:
            self._session.add(
                KnowledgeChunkModel(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    corpus_revision=revision,
                    ordinal=chunk.ordinal,
                    page=chunk.page,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    text=chunk.text,
                    text_sha256=chunk.text_sha256,
                    token_count=chunk.token_count,
                )
            )
        self._session.commit()

    def list_chunks_by_documents(
        self, document_ids: list[str]
    ) -> tuple[KnowledgeChunk, ...]:
        """按文档 ID 读切片（Phase 1 每文档一套切片，用于启动重建索引）。"""
        if not document_ids:
            return ()
        rows = (
            self._session.query(KnowledgeChunkModel)
            .filter(KnowledgeChunkModel.document_id.in_(document_ids))
            .order_by(
                KnowledgeChunkModel.document_id, KnowledgeChunkModel.ordinal
            )
            .all()
        )
        return tuple(
            KnowledgeChunk(
                id=str(row.id),
                document_id=str(row.document_id),
                ordinal=int(row.ordinal),
                page=int(row.page),
                char_start=int(row.char_start),
                char_end=int(row.char_end),
                text=str(row.text),
                text_sha256=str(row.text_sha256),
                token_count=int(row.token_count),
            )
            for row in rows
        )

    def get(self, document_id: str) -> PolicyDocument | None:
        model = self._session.get(PolicyDocumentModel, document_id)
        return self._to_entity(model) if model is not None else None

    def get_by_sha256(self, sha256: str) -> PolicyDocument | None:
        model = (
            self._session.query(PolicyDocumentModel)
            .filter(PolicyDocumentModel.sha256 == sha256)
            .one_or_none()
        )
        return self._to_entity(model) if model is not None else None

    def list_documents(
        self, status: DocumentStatus | None = None
    ) -> tuple[list[DocumentSummaryDTO], str]:
        query = self._session.query(PolicyDocumentModel)
        if status is not None:
            query = query.filter(PolicyDocumentModel.status == status.value)
        models = query.order_by(PolicyDocumentModel.created_at_utc).all()
        revision = self._active_revision()
        items = [self._to_summary(m, revision) for m in models]
        return items, revision

    def get_source_pdf(self, document_id: str, page: int) -> bytes:
        """按 document_id 查库取 source_relpath，读 PDF 取对应页（SPEC §8.6）。"""
        model = self._session.get(PolicyDocumentModel, document_id)
        if model is None:
            raise DocumentNotFoundError()
        if str(model.status) != DocumentStatus.ACTIVE.value:
            raise DocumentNotReadyError()
        if not model.source_relpath:
            raise DocumentNotReadyError()
        pdf_path = self._workspace_root / str(model.source_relpath)
        if not pdf_path.is_file():
            raise DocumentNotReadyError()

        reader = PdfReader(str(pdf_path))
        if page > len(reader.pages):
            raise PageOutOfRangeError()
        writer = PdfWriter()
        writer.add_page(reader.pages[page - 1])
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    def _active_revision(self) -> str:
        row = (
            self._session.query(CorpusRevisionModel)
            .filter(CorpusRevisionModel.status == "ACTIVE")
            .one_or_none()
        )
        return str(row.revision) if row is not None else ""

    @staticmethod
    def _to_entity(model: PolicyDocumentModel) -> PolicyDocument:
        return PolicyDocument(
            id=str(model.id),
            title=str(model.title),
            version=str(model.version),
            effective_at=cast(date | None, model.effective_at),
            expires_at=cast(date | None, model.expires_at),
            scope=str(model.scope),
            source_kind=str(model.source_kind),
            status=DocumentStatus(str(model.status)),
            sha256=str(model.sha256),
            page_count=cast(int | None, model.page_count),
            source_relpath=str(model.source_relpath) if model.source_relpath else None,
        )

    @staticmethod
    def _to_summary(model: PolicyDocumentModel, revision: str) -> DocumentSummaryDTO:
        return DocumentSummaryDTO(
            id=str(model.id),
            title=str(model.title),
            version=str(model.version),
            effective_at=cast(date | None, model.effective_at),
            expires_at=cast(date | None, model.expires_at),
            scope=str(model.scope),
            status=DocumentStatus(str(model.status)),
            page_count=cast(int | None, model.page_count),
            corpus_revision=revision,
        )
