"""健康检查接口（SPEC §8.2）。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from enterprise_policy_rag.domain.errors import ErrorCode
from enterprise_policy_rag.interfaces.api.dependencies import (
    HealthService,
    fail_envelope,
    get_health_service,
    get_trace_id,
    ok_envelope,
)

router = APIRouter()


@router.get("/health")
def health(
    service: Annotated[HealthService, Depends(get_health_service)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> Response:
    """GET /health：验证 API、SQLite、当前 corpus snapshot 可读。"""
    try:
        info = service.check()
    except Exception:
        # SPEC §8.2：health 失败返回 503 + INTERNAL_ERROR（区别于 §6.2 的 500 通用内部错误）。
        return JSONResponse(
            status_code=503,
            content=fail_envelope(
                ErrorCode.INTERNAL_ERROR, "服务不可用", trace_id
            ).model_dump(),
        )
    return JSONResponse(content=ok_envelope(info, trace_id).model_dump())
