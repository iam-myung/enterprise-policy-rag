"""制度导入编排（SPEC §8.3）。

IngestPolicy 编排：读取 → 解析 → 切片 → 建索引 → 事务内切换 revision。
失败路径不切换 active revision；同内容 sha256 返回 DUPLICATE_DOCUMENT。
可观测性：通过 TelemetryPort 记录解析/切片/建索引 span 与成败事件（SPEC §10.2）。
"""

import hashlib
import uuid
from pathlib import Path
from typing import Protocol

from enterprise_policy_rag.application.contracts.documents import DocumentSummaryDTO
from enterprise_policy_rag.application.ingestion.chunk_pages import chunk_pages
from enterprise_policy_rag.application.ports.document_parser import DocumentParserPort
from enterprise_policy_rag.application.ports.repositories import (
    CorpusRevisionRepositoryPort,
    DocumentRepositoryPort,
)
from enterprise_policy_rag.application.ports.telemetry import (
    TelemetryPort,
    noop_telemetry,
)
from enterprise_policy_rag.domain.entities import (
    DocumentStatus,
    KnowledgeChunk,
    ParsedPage,
    PolicyDocument,
)
from enterprise_policy_rag.domain.errors import ErrorCode
from enterprise_policy_rag.domain.result import ErrorDetail, OperationEnvelope


class IndexBuilder(Protocol):
    """索引构建抽象：给定完整语料 chunks + revision → index_relpath。"""

    def build(self, chunks: tuple[KnowledgeChunk, ...], revision: str) -> str: ...


class IngestPolicy:
    """IngestPolicy 编排（SPEC §8.3）。"""

    def __init__(
        self,
        parser: DocumentParserPort,
        document_repo: DocumentRepositoryPort,
        revision_repo: CorpusRevisionRepositoryPort,
        index_builder: IndexBuilder,
        workspace_root: Path,
        telemetry: TelemetryPort | None = None,
    ) -> None:
        self._parser = parser
        self._document_repo = document_repo
        self._revision_repo = revision_repo
        self._index_builder = index_builder
        self._workspace_root = workspace_root
        self._telemetry = telemetry if telemetry is not None else noop_telemetry()

    def ingest(
        self,
        file_path: Path,
        title: str,
        version: str,
        scope: str,
        source_kind: str,
    ) -> OperationEnvelope[DocumentSummaryDTO]:
        # 1. 计算内容 sha256 并做重复拦截
        sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if self._document_repo.get_by_sha256(sha) is not None:
            return self._fail(ErrorCode.DUPLICATE_DOCUMENT, "同内容文档已存在")

        # 2. 解析
        doc_id = uuid.uuid4().hex
        with self._telemetry.start_span("document.parse"):
            parsed = self._parser.parse(file_path, doc_id)

        # 3. 页内切片（纯函数）
        pages = tuple(
            ParsedPage(
                document_id=doc_id,
                page_number=p.page_number,
                source_text=p.source_text,
                source_text_sha256=p.source_text_sha256,
            )
            for p in parsed.pages
        )
        with self._telemetry.start_span("chunk.create"):
            chunks = chunk_pages(pages, doc_id, chunk_size=500)

        # 4. 累积语料：active 文档 + 本次文档；读旧切片合并成完整语料（SPEC §4.2）
        previous = self._revision_repo.get_active()
        previous_ids = list(previous.active_document_ids) if previous else []
        doc_ids = list(previous_ids)
        if doc_id not in doc_ids:
            doc_ids.append(doc_id)
        all_chunks = tuple(
            self._document_repo.list_chunks_by_documents(previous_ids)
        ) + chunks

        # 5. 生成新 revision 并建索引；失败不切换 revision
        revision = uuid.uuid4().hex
        try:
            with self._telemetry.start_span("index.build"):
                index_relpath = self._index_builder.build(all_chunks, revision)
        except Exception:
            return self._fail(ErrorCode.INDEX_BUILD_FAILED, "索引构建失败")

        # 6. 持久化页文本 + 本次切片（旧文档切片已落库，不重复写）
        self._document_repo.add_parsed_pages(pages)
        self._document_repo.add_chunks(chunks, revision)

        # 7. 事务内切换 revision + 保存文档
        self._revision_repo.activate(
            revision, index_relpath, _manifest_sha256(all_chunks), doc_ids
        )
        source_relpath = _rel_path(file_path, self._workspace_root)
        self._document_repo.add(
            PolicyDocument(
                id=doc_id,
                title=title,
                version=version,
                effective_at=None,
                expires_at=None,
                scope=scope,
                source_kind=source_kind,
                status=DocumentStatus.ACTIVE,
                sha256=sha,
                page_count=len(parsed.pages),
                source_relpath=source_relpath,
            )
        )

        # 8. 返回成功摘要
        summary = DocumentSummaryDTO(
            id=doc_id,
            title=title,
            version=version,
            effective_at=None,
            expires_at=None,
            scope=scope,
            status=DocumentStatus.ACTIVE,
            page_count=len(parsed.pages),
            corpus_revision=revision,
        )
        self._telemetry.record_event(
            "ingest.succeeded",
            (
                ("corpus_revision", revision),
                ("document_id", doc_id),
                ("page_count", str(len(parsed.pages))),
                ("chunk_count", str(len(chunks))),
            ),
        )
        self._telemetry.record_metric("ingest.success", 1.0)
        return OperationEnvelope(
            success=True,
            data=summary,
            error=None,
            message="ok",
            trace_id=uuid.uuid4().hex,
        )

    def _fail(self, code: ErrorCode, message: str) -> OperationEnvelope[DocumentSummaryDTO]:
        self._telemetry.record_event("ingest.failed", (("error_code", code.value),))
        self._telemetry.record_metric("ingest.failure", 1.0)
        return OperationEnvelope(
            success=False,
            data=None,
            error=ErrorDetail(code=code, message=message),
            message="request failed",
            trace_id=uuid.uuid4().hex,
        )


def _rel_path(file_path: Path, workspace_root: Path) -> str:
    """计算相对 workspace_root 的 source_relpath（SPEC §7.1：禁止绝对路径）。"""
    try:
        return file_path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return f"uploads/{file_path.name}"


def _manifest_sha256(chunks: tuple[KnowledgeChunk, ...]) -> str:
    """对 chunks 规范化清单取 sha256（SPEC §5.314 IndexReceipt.manifest_sha256）。"""
    ordered = sorted(chunks, key=lambda c: (c.document_id, c.ordinal))
    payload = "\n".join(
        f"{c.document_id}:{c.ordinal}:{c.text_sha256}" for c in ordered
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
