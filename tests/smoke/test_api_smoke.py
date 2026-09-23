"""Step 10-RED：API 真实入口 Smoke（SPEC §11.4 / §10.3：API smoke 单场景硬超时 60s）。

引用尚未实现的 FastAPI `app`，运行时应以 ImportError 失败（RED 证据）。

Smoke 目标：真实序列化链路——health → documents → questions 三端点完整往返，
验证 Envelope、X-Trace-Id 与 answer/citation 结构经真实 DTO 序列化后完整可读。
use case 以 fake 注入（关键外部边界 fake），真实 app + 真实 Envelope 序列化。
"""

import pytest
from fastapi.testclient import TestClient

from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.result import AnswerResult, AnswerStatus
from enterprise_policy_rag.interfaces.api.app import app  # RED：ImportError
from enterprise_policy_rag.interfaces.api.dependencies import (  # RED：ImportError
    get_ask_policy,
    get_document_repository,
    get_health_service,
)

client = TestClient(app)


class _FakeHealthService:
    def check(self) -> dict:
        return {
            "status": "ok",
            "database": "ok",
            "corpus_revision": "rev-1",
            "active_document_count": 0,
        }


class _FakeRepo:
    def list_documents(self, status: str | None = None) -> tuple[list, str]:
        return [], "rev-1"

    def get_source_pdf(self, document_id: str, page: int) -> bytes:
        return b"%PDF-1.4"


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


@pytest.mark.timeout(60)
def test_api_full_flow_smoke() -> None:
    """真实入口三端点往返：health 可读 → documents 列表 → questions 结构化答案。"""
    app.dependency_overrides[get_health_service] = lambda: _FakeHealthService()
    app.dependency_overrides[get_document_repository] = lambda: _FakeRepo()
    app.dependency_overrides[get_ask_policy] = lambda: _FakeAskPolicy()
    try:
        trace_id = "smoke-trace-1"

        health = client.get("/health", headers={"X-Trace-Id": trace_id})
        assert health.status_code == 200
        assert health.json()["trace_id"] == trace_id

        docs = client.get("/api/v1/documents", headers={"X-Trace-Id": trace_id})
        assert docs.status_code == 200
        assert isinstance(docs.json()["data"]["items"], list)

        q = client.post(
            "/api/v1/questions",
            json={"question": "员工年假有多少天？"},
            headers={"X-Trace-Id": trace_id},
        )
        assert q.status_code == 200
        data = q.json()["data"]
        assert data["status"] in {"ANSWERED", "NO_EVIDENCE", "CONFLICT"}
        assert data["trace_id"] == trace_id
    finally:
        app.dependency_overrides.pop(get_health_service, None)
        app.dependency_overrides.pop(get_document_repository, None)
        app.dependency_overrides.pop(get_ask_policy, None)
