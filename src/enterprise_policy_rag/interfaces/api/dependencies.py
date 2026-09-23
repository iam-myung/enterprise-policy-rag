"""FastAPI 依赖注入与 Envelope 构造（SPEC §2.1 interfaces / §6.1）。

依赖从 `app.state` 读取，由 composition 装配；测试通过 `dependency_overrides` 注入 fake。
"""

import uuid
from typing import Any, Protocol, cast

from fastapi import Header, Request

from enterprise_policy_rag.application.contracts.documents import DocumentSummaryDTO
from enterprise_policy_rag.application.contracts.envelope import EnvelopeDTO, ErrorDTO
from enterprise_policy_rag.domain.entities import DocumentStatus
from enterprise_policy_rag.domain.errors import ErrorCode
from enterprise_policy_rag.domain.result import AnswerResult


class HealthService(Protocol):
    def check(self) -> dict[str, Any]: ...


class DocumentQuery(Protocol):
    def list_documents(
        self, status: DocumentStatus | None
    ) -> tuple[list[DocumentSummaryDTO], str]: ...

    def get_source_pdf(self, document_id: str, page: int) -> bytes:
        """返回对应页 PDF 字节；不存在抛 DocumentNotFoundError，未就绪抛 DocumentNotReadyError。"""
        ...


class AskPolicy(Protocol):
    def ask(self, question: str) -> AnswerResult: ...


def get_trace_id(
    x_trace_id: str | None = Header(None, alias="X-Trace-Id"),
) -> str:
    """透传 X-Trace-Id；缺省时生成（SPEC §8.1）。"""
    return x_trace_id or uuid.uuid4().hex


def get_health_service(request: Request) -> HealthService:
    # getattr 缺省 None：未 wire 时依赖解析不抛异常，交由请求校验（422）或端点兜底。
    return cast(HealthService, getattr(request.app.state, "health_service", None))


def get_document_repository(request: Request) -> DocumentQuery:
    return cast(DocumentQuery, getattr(request.app.state, "document_repository", None))


def get_ask_policy(request: Request) -> AskPolicy:
    return cast(AskPolicy, getattr(request.app.state, "ask_policy", None))


def ok_envelope(data: Any, trace_id: str) -> EnvelopeDTO:
    """成功 Envelope（SPEC §6.1）。"""
    return EnvelopeDTO(success=True, data=data, error=None, message="ok", trace_id=trace_id)


def fail_envelope(code: ErrorCode, message: str, trace_id: str) -> EnvelopeDTO:
    """失败 Envelope（SPEC §6.1）。"""
    return EnvelopeDTO(
        success=False,
        data=None,
        error=ErrorDTO(code=code.value, message=message),
        message="request failed",
        trace_id=trace_id,
    )
