"""Step 10-RED：HTTP 合同测试（SPEC §6.1 Envelope / §8.1–8.6 端点）。

引用尚未实现的 FastAPI `app` 与依赖注入函数，运行时应以 ImportError 失败（RED 证据）。

依赖注入契约（GREEN 阶段在 interfaces/api/dependencies.py 提供）：
- get_health_service：health 端点；返回对象需提供 check() -> dict
- get_document_repository：documents / source 端点；返回对象需提供
  list_documents(status) -> (items, revision) 与 get_source_pdf(doc_id, page) -> bytes|None
- get_ask_policy：questions 端点；返回对象需提供 ask(question) -> AnswerResult
"""

from fastapi.testclient import TestClient

from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.errors import (
    AppError,
    DocumentNotFoundError,
    DocumentNotReadyError,
    ErrorCode,
    PageOutOfRangeError,
)
from enterprise_policy_rag.domain.result import AnswerResult, AnswerStatus
from enterprise_policy_rag.interfaces.api.app import app  # RED：ImportError
from enterprise_policy_rag.interfaces.api.dependencies import (  # RED：ImportError
    get_ask_policy,
    get_document_repository,
    get_health_service,
)

client = TestClient(app)


# ---------- 通用 Envelope + Trace-Id（SPEC §6.1 / §8.1） ----------


def test_trace_id_passthrough() -> None:
    """请求透传 X-Trace-Id：响应返回同一 trace id。"""
    app.dependency_overrides[get_health_service] = lambda: _FakeHealthService()
    try:
        resp = client.get("/health", headers={"X-Trace-Id": "trace-abc-123"})
    finally:
        app.dependency_overrides.pop(get_health_service, None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["trace_id"] == "trace-abc-123"


def test_envelope_success_mutual_exclusion() -> None:
    """成功 Envelope：success=true ⇒ data 非空且 error=null。"""
    app.dependency_overrides[get_health_service] = lambda: _FakeHealthService()
    try:
        resp = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_health_service, None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] is not None
    assert body["error"] is None


def test_envelope_failure_mutual_exclusion() -> None:
    """失败 Envelope：success=false ⇒ data=null 且 error 非空（422 参数非法触发）。"""
    resp = client.post("/api/v1/questions", json={"question": "", "top_k": 99})
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"] is not None


# ---------- ① GET /health（SPEC §8.2） ----------


def test_health_ok_shape() -> None:
    """200 data 含 status/database/corpus_revision/active_document_count。"""
    app.dependency_overrides[get_health_service] = lambda: _FakeHealthService()
    try:
        resp = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_health_service, None)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {"status", "database", "corpus_revision", "active_document_count"} <= data.keys()


def test_health_internal_error_503() -> None:
    """database 不可读 → 503 INTERNAL_ERROR，不泄露连接串/绝对路径。"""
    app.dependency_overrides[get_health_service] = lambda: _FailingHealthService()
    try:
        resp = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_health_service, None)
    assert resp.status_code == 503
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
    # 不得回显连接串或绝对路径
    assert "sqlite" not in str(body).lower()
    assert ":" not in body["error"]["message"]


# ---------- ② GET /api/v1/documents（SPEC §8.4） ----------


def test_documents_ok_shape() -> None:
    """200 data 含 items（列表）与 corpus_revision。"""
    app.dependency_overrides[get_document_repository] = lambda: _FakeRepo()
    try:
        resp = client.get("/api/v1/documents")
    finally:
        app.dependency_overrides.pop(get_document_repository, None)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data["items"], list)
    assert "corpus_revision" in data


def test_documents_invalid_status_422() -> None:
    """status 非法枚举 → 422 VALIDATION_ERROR。"""
    resp = client.get("/api/v1/documents", params={"status": "NOT_A_STATUS"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------- ③ POST /api/v1/questions（SPEC §8.5） ----------


def test_questions_ok_shape() -> None:
    """200 data 含 status/answer/citations/warnings/corpus_revision/trace_id。"""
    app.dependency_overrides[get_ask_policy] = lambda: _FakeAskPolicy()
    try:
        resp = client.post("/api/v1/questions", json={"question": "年假多少天"})
    finally:
        app.dependency_overrides.pop(get_ask_policy, None)
    assert resp.status_code == 200
    data = resp.json()["data"]
    keys = {
        "status",
        "answer",
        "citations",
        "warnings",
        "corpus_revision",
        "confidence",
        "trace_id",
    }
    assert keys <= data.keys()


def test_questions_citation_source_url_relative() -> None:
    """CitationDTO 的 source_url 必须是站内相对路径（由 API 生成，不采信模型/用户）。"""
    app.dependency_overrides[get_ask_policy] = lambda: _FakeAskPolicy()
    try:
        resp = client.post("/api/v1/questions", json={"question": "年假多少天"})
    finally:
        app.dependency_overrides.pop(get_ask_policy, None)
    citations = resp.json()["data"]["citations"]
    assert citations, "ANSWERED 场景 citations 非空"
    for c in citations:
        assert "source_url" in c
        assert c["source_url"].startswith("/api/v1/")
        assert "http://" not in c["source_url"] and "https://" not in c["source_url"]


def test_questions_top_k_bounds_422() -> None:
    """top_k 范围 1–10：0 与 11 均 → 422 VALIDATION_ERROR。"""
    assert client.post("/api/v1/questions", json={"question": "q", "top_k": 0}).status_code == 422
    assert client.post("/api/v1/questions", json={"question": "q", "top_k": 11}).status_code == 422


def test_questions_question_length_422() -> None:
    """question 长度 1–1000：空串与超长均 → 422 VALIDATION_ERROR。"""
    assert client.post("/api/v1/questions", json={"question": ""}).status_code == 422
    too_long = "问" * 1001
    assert client.post("/api/v1/questions", json={"question": too_long}).status_code == 422


def test_questions_provider_failure_502() -> None:
    """Provider 失败（AppError）→ 502 且映射 LLM_PROVIDER_ERROR。"""
    app.dependency_overrides[get_ask_policy] = lambda: _FailingAskPolicy()
    try:
        resp = client.post("/api/v1/questions", json={"question": "年假多少天"})
    finally:
        app.dependency_overrides.pop(get_ask_policy, None)
    assert resp.status_code == 502
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "LLM_PROVIDER_ERROR"


# ---------- ④ GET /api/v1/documents/{id}/source（SPEC §8.6） ----------


def test_source_ok_pdf_stream() -> None:
    """200：返回 PDF 内容流，并设置安全 Content-Disposition。"""
    app.dependency_overrides[get_document_repository] = lambda: _FakeRepo(mode="ok")
    try:
        resp = client.get("/api/v1/documents/doc-1/source", params={"page": 1})
    finally:
        app.dependency_overrides.pop(get_document_repository, None)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert "inline" in resp.headers.get("content-disposition", "").lower()


def test_source_not_found_404() -> None:
    """document_id 不存在 → 404 DOCUMENT_NOT_FOUND。"""
    app.dependency_overrides[get_document_repository] = lambda: _FakeRepo(mode="not_found")
    try:
        resp = client.get("/api/v1/documents/ghost/source", params={"page": 1})
    finally:
        app.dependency_overrides.pop(get_document_repository, None)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_source_not_ready_409() -> None:
    """document 状态未就绪 → 409 DOCUMENT_NOT_READY。"""
    app.dependency_overrides[get_document_repository] = lambda: _FakeRepo(mode="not_ready")
    try:
        resp = client.get("/api/v1/documents/doc-1/source", params={"page": 1})
    finally:
        app.dependency_overrides.pop(get_document_repository, None)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DOCUMENT_NOT_READY"


def test_source_page_out_of_range_422() -> None:
    """page 越界（> 总页数）→ 422 VALIDATION_ERROR（QA 回归：原误映射 409）。"""
    app.dependency_overrides[get_document_repository] = (
        lambda: _FakeRepo(mode="page_out_of_range")
    )
    try:
        resp = client.get("/api/v1/documents/doc-1/source", params={"page": 99})
    finally:
        app.dependency_overrides.pop(get_document_repository, None)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_source_invalid_page_422() -> None:
    """page 非法（非整数）→ 422 VALIDATION_ERROR。"""
    resp = client.get("/api/v1/documents/doc-1/source", params={"page": "abc"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------- Fakes（测试替身，定义端点所需 use case 方法契约） ----------


class _FakeHealthService:
    def check(self) -> dict:
        return {
            "status": "ok",
            "database": "ok",
            "corpus_revision": "rev-1",
            "active_document_count": 0,
        }


class _FailingHealthService:
    def check(self) -> dict:
        raise RuntimeError("db down")


class _FakeRepo:
    def __init__(self, mode: str = "ok") -> None:
        self._mode = mode  # "ok" | "not_found" | "not_ready" | "page_out_of_range"

    def list_documents(self, status: str | None = None) -> tuple[list, str]:
        return [], "rev-1"

    def get_source_pdf(self, document_id: str, page: int) -> bytes:
        if self._mode == "not_found":
            raise DocumentNotFoundError()
        if self._mode == "not_ready":
            raise DocumentNotReadyError()
        if self._mode == "page_out_of_range":
            raise PageOutOfRangeError()
        return b"%PDF-1.4 fake"


_EVIDENCE = Evidence(
    evidence_id="e1",
    chunk_id="c1",
    document_id="doc-1",
    title="年假制度",
    version="v1",
    page=1,
    char_start=0,
    char_end=5,
    quote="年假十五天",
    page_text_sha256="0" * 64,
    score=1.0,
)


class _FakeAskPolicy:
    def ask(self, question: str) -> AnswerResult:
        return AnswerResult(
            status=AnswerStatus.ANSWERED,
            answer="年假十五天",
            citations=(_EVIDENCE,),
            warnings=(),
            corpus_revision="rev-1",
            confidence=0.85,
        )


class _FailingAskPolicy:
    def ask(self, question: str) -> AnswerResult:
        raise AppError(ErrorCode.LLM_PROVIDER_ERROR, "回答模型 Provider 失败")


class _RuntimeErrorAskPolicy:
    def ask(self, question: str) -> AnswerResult:
        raise RuntimeError("unexpected boom")


def test_unhandled_exception_returns_500_envelope() -> None:
    """未预期异常 → 500 INTERNAL_ERROR 统一 Envelope（QA 回归：缺全局兜底）。"""
    app.dependency_overrides[get_ask_policy] = lambda: _RuntimeErrorAskPolicy()
    c = TestClient(app, raise_server_exceptions=False)
    try:
        resp = c.post(
            "/api/v1/questions", json={"question": "年假多少天", "top_k": 5}
        )
    finally:
        app.dependency_overrides.pop(get_ask_policy, None)
    assert resp.status_code == 500
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
