"""问答接口（SPEC §8.5）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from enterprise_policy_rag.application.contracts.questions import (
    CitationDTO,
    QuestionAnswerDTO,
    QuestionRequestDTO,
)
from enterprise_policy_rag.domain.errors import AppError
from enterprise_policy_rag.interfaces.api.dependencies import (
    AskPolicy,
    fail_envelope,
    get_ask_policy,
    get_trace_id,
    ok_envelope,
)

router = APIRouter()


@router.post("/api/v1/questions")
def ask_question(
    req: QuestionRequestDTO,
    policy: Annotated[AskPolicy, Depends(get_ask_policy)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> Response:
    """POST /api/v1/questions：基于当前不可变 corpus snapshot 回答（SPEC §8.5）。

    source_url 由 API 根据 document_id 与 page 生成站内相对路径，不采信模型/用户。
    """
    try:
        result = policy.ask(req.question)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.code.http_status,
            content=fail_envelope(exc.code, exc.message, trace_id).model_dump(),
        )
    citations = [
        CitationDTO(
            evidence_id=e.evidence_id,
            document_id=e.document_id,
            title=e.title,
            version=e.version,
            effective_at=None,
            page=e.page,
            quote=e.quote,
            char_start=e.char_start,
            char_end=e.char_end,
            page_text_sha256=e.page_text_sha256,
            source_url=f"/api/v1/documents/{e.document_id}/source?page={e.page}",
        )
        for e in result.citations
    ]
    dto = QuestionAnswerDTO(
        status=result.status.value,
        answer=result.answer,
        citations=citations,
        warnings=list(result.warnings),
        corpus_revision=result.corpus_revision,
        confidence=result.confidence,
        trace_id=trace_id,
    )
    return JSONResponse(content=ok_envelope(dto, trace_id).model_dump())
