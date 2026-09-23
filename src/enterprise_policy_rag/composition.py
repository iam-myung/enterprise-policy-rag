"""应用装配入口（SPEC §2.1）。

composition 是唯一装配入口：把 SQLite 仓储、FAISS/BM25 混合索引、重排/冲突/回答
模型装配成可运行的依赖图；禁止全局可变单例与隐式客户端初始化。
"""

import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from enterprise_policy_rag.adapters.document.pypdf_parser import PypdfParser
from enterprise_policy_rag.adapters.llm.conflict_detector import QwenConflictDetector
from enterprise_policy_rag.adapters.llm.dashscope_embeddings import DashScopeEmbeddings
from enterprise_policy_rag.adapters.llm.dashscope_providers import (
    chat_provider,
    conflict_provider,
    rerank_provider,
)
from enterprise_policy_rag.adapters.llm.qwen_chat_model import QwenChatModel
from enterprise_policy_rag.adapters.persistence.document_repository import (
    CorpusRevisionRepository,
    DocumentRepository,
)
from enterprise_policy_rag.adapters.persistence.sqlite_models import Base
from enterprise_policy_rag.adapters.retrieval.bm25_index import BM25Index
from enterprise_policy_rag.adapters.retrieval.faiss_index import FaissIndex
from enterprise_policy_rag.adapters.retrieval.qwen_reranker import QwenReranker
from enterprise_policy_rag.application.contracts.documents import DocumentSummaryDTO
from enterprise_policy_rag.application.contracts.evaluations import PipelineResult
from enterprise_policy_rag.application.ingestion.ingest_policy import IngestPolicy
from enterprise_policy_rag.application.ports.models import RerankResultDTO
from enterprise_policy_rag.application.ports.telemetry import TelemetryPort, noop_telemetry
from enterprise_policy_rag.application.qa.ask_policy import AskPolicy
from enterprise_policy_rag.application.qa.rrf_fusion import rrf_fusion
from enterprise_policy_rag.domain.entities import Evidence, KnowledgeChunk
from enterprise_policy_rag.domain.result import AnswerResult, OperationEnvelope


class HybridIndex:
    """稠密 + 稀疏混合索引（内存）：导入构建，问答检索（SPEC §9.2）。"""

    def __init__(
        self, dense: FaissIndex, sparse: BM25Index, rrf_k: int = 60
    ) -> None:
        self._dense = dense
        self._sparse = sparse
        self._rrf_k = rrf_k
        self._chunks: dict[str, dict[str, KnowledgeChunk]] = {}
        self._page_texts: dict[str, str] = {}
        self._active_revision = ""

    @property
    def active_revision(self) -> str:
        return self._active_revision

    @property
    def page_texts(self) -> dict[str, str]:
        return self._page_texts

    def build(self, chunks: tuple[KnowledgeChunk, ...], revision: str) -> str:
        self._dense.build(chunks, revision)
        self._sparse.build(chunks, revision)
        self._chunks[revision] = {c.id: c for c in chunks}
        self._page_texts.clear()
        self._page_texts.update(_build_page_texts(chunks))
        self._active_revision = revision
        # index_relpath 形如 "<dir>/<revision>"（相对 workspace/indexes），
        # IngestPolicy 以末段作为 revision（SPEC §7.1 corpus_revisions.index_relpath）。
        return f"index/{revision}"

    def retrieve(
        self, question: str, top_k: int, doc_repo: DocumentRepository
    ) -> tuple[Evidence, ...]:
        revision = self._active_revision
        if not revision:
            return ()
        dense = self._dense.query(question, revision, 20)
        sparse = self._sparse.query(question, revision, 20)
        fused = rrf_fusion(
            tuple(c.chunk_id for c in dense),
            tuple(c.chunk_id for c in sparse),
            k=self._rrf_k,
        )
        return self._to_evidence(
            tuple(fc.candidate_id for fc in fused[:top_k]),
            tuple(fc.rrf_score for fc in fused[:top_k]),
            revision,
            doc_repo,
        )

    def retrieve_dense_only(
        self, question: str, top_k: int, doc_repo: DocumentRepository
    ) -> tuple[Evidence, ...]:
        """纯向量基线检索（SPEC §9.4）：只用 dense，不用 BM25/RRF。"""
        revision = self._active_revision
        if not revision:
            return ()
        dense = self._dense.query(question, revision, top_k)
        return self._to_evidence(
            tuple(c.chunk_id for c in dense),
            tuple(-c.distance for c in dense),  # L2 距离越小越相关，取负作分数
            revision,
            doc_repo,
        )

    def _to_evidence(
        self,
        chunk_ids: tuple[str, ...],
        scores: tuple[float, ...],
        revision: str,
        doc_repo: DocumentRepository,
    ) -> tuple[Evidence, ...]:
        chunks = self._chunks[revision]
        evidence: list[Evidence] = []
        for chunk_id, score in zip(chunk_ids, scores, strict=True):
            chunk = chunks.get(chunk_id)
            if chunk is None:
                continue
            doc = doc_repo.get(chunk.document_id)
            evidence.append(
                Evidence(
                    evidence_id=chunk.id,
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    title=doc.title if doc else "",
                    version=doc.version if doc else "",
                    page=chunk.page,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    quote=chunk.text,
                    page_text_sha256=chunk.text_sha256,
                    score=score,
                )
            )
        return tuple(evidence)


def _build_page_texts(chunks: tuple[KnowledgeChunk, ...]) -> dict[str, str]:
    """从页内切片重建页文本（chunk 按 char_start 排序拼接）。"""
    grouped: dict[tuple[str, int], list[KnowledgeChunk]] = {}
    for c in chunks:
        grouped.setdefault((c.document_id, c.page), []).append(c)
    page_texts: dict[str, str] = {}
    for chunks_in_page in grouped.values():
        ordered = sorted(chunks_in_page, key=lambda c: c.char_start)
        page_text = "".join(c.text for c in ordered)
        for c in ordered:
            page_texts[c.id] = page_text
    return page_texts


class HybridIndexBuilder:
    """把 HybridIndex 适配为 IngestPolicy 的 IndexBuilder（SPEC §5.314）。

    给定完整语料 chunks + revision → 构建索引并返回 index_relpath。
    """

    def __init__(self, hybrid: HybridIndex) -> None:
        self._hybrid = hybrid

    def build(
        self, chunks: tuple[KnowledgeChunk, ...], revision: str
    ) -> str:
        return self._hybrid.build(chunks, revision)


class _HealthService:
    """健康检查（SPEC §8.2）：验证 SQLite + 当前 corpus revision 可读。"""

    def __init__(self, revision_repo: CorpusRevisionRepository) -> None:
        self._revision_repo = revision_repo

    def check(self) -> dict[str, object]:
        active = self._revision_repo.get_active()
        return {
            "status": "ok",
            "database": "ok",
            "corpus_revision": active.revision if active else "",
            "active_document_count": len(active.active_document_ids) if active else 0,
        }


@dataclass
class AppContainer:
    """装配后的依赖图。"""

    ingest_policy: IngestPolicy
    ask_policy: AskPolicy
    document_repository: DocumentRepository
    health_service: _HealthService
    hybrid: HybridIndex
    telemetry: TelemetryPort
    session: Session

    def ingest(
        self, file_path: Path, title: str, version: str, scope: str, source_kind: str
    ) -> OperationEnvelope[DocumentSummaryDTO]:
        result = self.ingest_policy.ingest(
            file_path, title, version, scope, source_kind
        )
        if result.success and result.data is not None:
            self.ask_policy._corpus_revision = result.data.corpus_revision  # noqa: SLF001
        return result

    def ask(self, question: str) -> AnswerResult:
        return self.ask_policy.ask(question)


class _PassthroughReranker:
    """纯向量基线用的不重排 reranker（SPEC §9.4：基线不含 rerank）。"""

    def rerank(
        self, question: str, candidates: tuple[Evidence, ...]
    ) -> RerankResultDTO:
        return RerankResultDTO(
            evidence_ids=tuple(c.evidence_id for c in candidates), degraded=False
        )


class RagEvaluationPipeline:
    """评测管线（SPEC §7.2）：retriever 取候选 + AskPolicy.answer 作答。"""

    def __init__(
        self,
        retriever: Callable[[str], tuple[Evidence, ...]],
        ask_policy: AskPolicy,
        telemetry: TelemetryPort | None = None,
    ) -> None:
        self._retriever = retriever
        self._ask_policy = ask_policy
        self._telemetry = telemetry if telemetry is not None else noop_telemetry()

    def run(self, question: str) -> PipelineResult:
        with self._telemetry.start_span("evaluate.run"):
            start = time.perf_counter()
            candidates = self._retriever(question)
            result = self._ask_policy.answer(question, candidates)
            latency_ms = (time.perf_counter() - start) * 1000
        degraded = "RERANKER_DEGRADED" in result.warnings
        self._telemetry.record_event(
            "evaluate.sample",
            (
                ("status", result.status.value),
                ("evidence_count", str(len(candidates))),
                ("degraded", "true" if degraded else "false"),
                ("latency_ms", str(round(latency_ms, 3))),
            ),
        )
        self._telemetry.record_metric("evaluate.latency_ms", latency_ms)
        if degraded:
            self._telemetry.record_metric("evaluate.degraded", 1.0)
        return PipelineResult(
            status=result.status.value,
            answer=result.answer,
            citations=result.citations,
            candidates=candidates,
            latency_ms=latency_ms,
            degraded=degraded,
        )


def build_evaluation_pipelines(
    container: AppContainer,
) -> tuple[RagEvaluationPipeline, RagEvaluationPipeline]:
    """装配 baseline（纯向量 top5）与 target（混合+RRF+rerank）（SPEC §9.4）。"""
    doc_repo = container.document_repository
    hybrid = container.hybrid
    page_texts = hybrid.page_texts
    corpus_revision = hybrid.active_revision

    chat_model = QwenChatModel(chat_provider)
    conflict_detector = QwenConflictDetector(conflict_provider)

    top_k = _read_top_k()

    def baseline_retriever(question: str) -> tuple[Evidence, ...]:
        return hybrid.retrieve_dense_only(question, top_k, doc_repo)

    def target_retriever(question: str) -> tuple[Evidence, ...]:
        return hybrid.retrieve(question, top_k, doc_repo)

    threshold = _read_evidence_threshold()
    baseline_ask = AskPolicy(
        baseline_retriever,
        _PassthroughReranker(),
        conflict_detector,
        chat_model,
        page_texts,
        corpus_revision,
        evidence_threshold=threshold,
        telemetry=container.telemetry,
    )
    target_ask = AskPolicy(
        target_retriever,
        QwenReranker(rerank_provider),
        conflict_detector,
        chat_model,
        page_texts,
        corpus_revision,
        evidence_threshold=threshold,
        telemetry=container.telemetry,
    )

    return (
        RagEvaluationPipeline(baseline_retriever, baseline_ask, container.telemetry),
        RagEvaluationPipeline(target_retriever, target_ask, container.telemetry),
    )


def _ensure_sqlite_dir(database_url: str) -> None:
    """创建 SQLite 数据库文件的父目录（容器空 volume 下缺失会致建库失败）。"""
    url = make_url(database_url)
    if url.database:
        db_file = Path(url.database)
        if not db_file.is_absolute():
            db_file = Path.cwd() / db_file
        db_file.parent.mkdir(parents=True, exist_ok=True)


def build_container(workspace_root: Path, database_url: str) -> AppContainer:
    """唯一装配入口：构建完整依赖图。"""
    workspace_root.mkdir(parents=True, exist_ok=True)
    _ensure_sqlite_dir(database_url)
    engine = create_engine(database_url)
    # demo 快速建表（生产环境应由 Alembic 迁移管理，SPEC §7.3）
    Base.metadata.create_all(engine)
    session = Session(engine)

    doc_repo = DocumentRepository(session, workspace_root)
    revision_repo = CorpusRevisionRepository(session)
    parser = PypdfParser()

    embedder = DashScopeEmbeddings(
        model="text-embedding-v3", timeout=_read_provider_timeout()
    )
    dense = FaissIndex(embedder)
    sparse = BM25Index()
    hybrid = HybridIndex(dense, sparse, rrf_k=_read_rrf_k())

    # 启动重建：从 SQLite 读 active revision 的文档切片，重建索引（SPEC §10.1）。
    snapshot = revision_repo.get_active()
    if snapshot:
        chunks = doc_repo.list_chunks_by_documents(
            list(snapshot.active_document_ids)
        )
        hybrid.build(chunks, snapshot.revision)

    telemetry = _build_telemetry()

    ingest_policy = IngestPolicy(
        parser,
        doc_repo,
        revision_repo,
        HybridIndexBuilder(hybrid),
        workspace_root,
        telemetry=telemetry,
    )

    chat_model = QwenChatModel(chat_provider)
    reranker = QwenReranker(rerank_provider)
    conflict_detector = QwenConflictDetector(conflict_provider)

    top_k = _read_top_k()

    def retriever(question: str) -> tuple[Evidence, ...]:
        return hybrid.retrieve(question, top_k, doc_repo)

    ask_policy = AskPolicy(
        retriever,
        reranker,
        conflict_detector,
        chat_model,
        hybrid.page_texts,
        corpus_revision=hybrid.active_revision,
        evidence_threshold=_read_evidence_threshold(),
        telemetry=telemetry,
    )

    return AppContainer(
        ingest_policy=ingest_policy,
        ask_policy=ask_policy,
        document_repository=doc_repo,
        health_service=_HealthService(revision_repo),
        hybrid=hybrid,
        telemetry=telemetry,
        session=session,
    )


def _workspace_from_env() -> tuple[Path, str]:
    """从环境变量读取 workspace 根与数据库连接串（入口处加载 .env）。"""
    from dotenv import load_dotenv

    load_dotenv()
    workspace = Path(os.environ.get("WORKSPACE_ROOT", "workspace"))
    database_url = os.environ.get(
        "DATABASE_URL", "sqlite:///workspace/database/enterprise_policy_rag.db"
    )
    return workspace, database_url


def _read_evidence_threshold() -> float:
    """从环境变量读取证据强度阈值（SPEC §12 RAG_EVIDENCE_THRESHOLD）。"""
    raw = os.environ.get("RAG_EVIDENCE_THRESHOLD", "0.0").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _read_top_k() -> int:
    """从环境变量读取检索返回条数（SPEC §9 RAG_TOP_K）。"""
    raw = os.environ.get("RAG_TOP_K", "5").strip()
    try:
        return int(raw)
    except ValueError:
        return 5


def _read_rrf_k() -> int:
    """从环境变量读取 RRF 融合常数（SPEC §9.2 RAG_RRF_K）。"""
    raw = os.environ.get("RAG_RRF_K", "60").strip()
    try:
        return int(raw)
    except ValueError:
        return 60


def _read_provider_timeout() -> float:
    """从环境变量读取 Provider 调用超时秒数（SPEC §9.4 PROVIDER_TIMEOUT_SECONDS）。"""
    raw = os.environ.get("PROVIDER_TIMEOUT_SECONDS", "30").strip()
    try:
        return float(raw)
    except ValueError:
        return 30.0


def _build_telemetry() -> TelemetryPort:
    """装配可观测性（SPEC §10.2）：OTEL_ENABLED 关闭时 no-op，否则用 OTel 适配器。"""
    from enterprise_policy_rag.adapters.telemetry.otel_telemetry import (
        OtelTelemetry,
    )

    flag = os.environ.get("OTEL_ENABLED", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return noop_telemetry()
    return OtelTelemetry()


def create_app() -> FastAPI:
    """装配并返回 FastAPI app（Composition Root，SPEC §2.1）。

    uvicorn 以 --factory 模式启动：
    `uvicorn enterprise_policy_rag.composition:create_app --factory`。
    """
    from enterprise_policy_rag.interfaces.api.app import app

    workspace, database_url = _workspace_from_env()
    container = build_container(workspace, database_url)
    app.state.health_service = container.health_service
    app.state.document_repository = container.document_repository
    app.state.ask_policy = container.ask_policy
    return app


def ingest_main(argv: list[str] | None = None) -> int:
    """制度导入 CLI 入口（Composition Root，SPEC §8.3）。"""
    from enterprise_policy_rag.interfaces.cli.ingest import run

    workspace, database_url = _workspace_from_env()
    container = build_container(workspace, database_url)
    return run(container, argv)


def evaluate_main(argv: list[str] | None = None) -> int:
    """评测 CLI 入口（Composition Root，SPEC §7.2）。"""
    from enterprise_policy_rag.interfaces.cli.evaluate import run

    workspace, database_url = _workspace_from_env()
    container = build_container(workspace, database_url)
    baseline, target = build_evaluation_pipelines(container)
    return run(
        baseline,
        target,
        container.hybrid.active_revision,
        argv,
        telemetry=container.telemetry,
    )


def main(argv: list[str] | None = None) -> int:
    """统一 CLI 入口：`python -m enterprise_policy_rag.composition <ingest|evaluate> ...`。"""
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(
            "用法: python -m enterprise_policy_rag.composition <ingest|evaluate> ...",
            file=sys.stderr,
        )
        return 2
    command, rest = argv[0], argv[1:]
    if command == "ingest":
        return ingest_main(rest)
    if command == "evaluate":
        return evaluate_main(rest)
    print(f"未知命令: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
