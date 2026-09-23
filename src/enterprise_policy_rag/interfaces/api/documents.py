"""文档接口（SPEC §8.4 / §8.6）。"""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response

from enterprise_policy_rag.domain.entities import DocumentStatus
from enterprise_policy_rag.domain.errors import (
    DocumentNotFoundError,
    DocumentNotReadyError,
    ErrorCode,
    PageOutOfRangeError,
)
from enterprise_policy_rag.interfaces.api.dependencies import (
    DocumentQuery,
    fail_envelope,
    get_document_repository,
    get_trace_id,
    ok_envelope,
)

router = APIRouter()


@router.get("/api/v1/documents")
def list_documents(
    repo: Annotated[DocumentQuery, Depends(get_document_repository)],
    trace_id: Annotated[str, Depends(get_trace_id)],
    status: Annotated[DocumentStatus | None, Query()] = None,
) -> Response:
    """GET /api/v1/documents：展示已导入制度及其状态（SPEC §8.4）。"""
    items, revision = repo.list_documents(status)
    item_dicts = [asdict(item) if not isinstance(item, dict) else item for item in items]
    return JSONResponse(
        content=ok_envelope(
            {"items": item_dicts, "corpus_revision": revision}, trace_id
        ).model_dump()
    )


@router.get("/api/v1/documents/{document_id}/source")
def get_source(
    document_id: str,
    page: Annotated[int, Query(ge=1)],
    repo: Annotated[DocumentQuery, Depends(get_document_repository)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> Response:
    """GET /api/v1/documents/{id}/source：回看引用对应 PDF 页（SPEC §8.6）。

    source_url 由 API 根据 document_id 与 page 生成；本端点只按 document_id 查库，
    拒绝用户提交的任意文件路径。
    """
    try:
        pdf = repo.get_source_pdf(document_id, page)
    except DocumentNotFoundError:
        return JSONResponse(
            status_code=ErrorCode.DOCUMENT_NOT_FOUND.http_status,
            content=fail_envelope(
                ErrorCode.DOCUMENT_NOT_FOUND, "文档不存在", trace_id
            ).model_dump(),
        )
    except DocumentNotReadyError:
        return JSONResponse(
            status_code=ErrorCode.DOCUMENT_NOT_READY.http_status,
            content=fail_envelope(
                ErrorCode.DOCUMENT_NOT_READY, "文档未就绪", trace_id
            ).model_dump(),
        )
    except PageOutOfRangeError:
        return JSONResponse(
            status_code=ErrorCode.VALIDATION_ERROR.http_status,
            content=fail_envelope(
                ErrorCode.VALIDATION_ERROR, "页码越界", trace_id
            ).model_dump(),
        )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{document_id}_p{page}.pdf"',
        },
    )
