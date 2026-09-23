"""FastAPI 应用入口（SPEC §6.1 / §8.1）。

只定义 app 与路由、统一 Envelope 异常处理与 X-Trace-Id 透传；
依赖由 composition 装配到 `app.state`（Composition Root，SPEC §2.1）。
测试通过 `dependency_overrides` 注入 fake。
"""

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from enterprise_policy_rag.application.contracts.envelope import EnvelopeDTO, ErrorDTO
from enterprise_policy_rag.interfaces.api import documents, health, questions

app = FastAPI(title="Enterprise Policy RAG", version="0.1.0")

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(questions.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """请求校验失败 → 422 VALIDATION_ERROR（SPEC §6.2）。"""
    trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
    envelope = EnvelopeDTO(
        success=False,
        data=None,
        error=ErrorDTO(code="VALIDATION_ERROR", message="请求参数非法"),
        message="request failed",
        trace_id=trace_id,
    )
    return JSONResponse(status_code=422, content=envelope.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """未预期异常兜底 → 500 INTERNAL_ERROR，统一 Envelope（SPEC §6.1）。

    AppError 已在各端点内捕获；此处只处理漏网的异常。HTTPException（如 404
    路由不存在）保持原状态码与 detail，不误判为 500。
    """
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
    envelope = EnvelopeDTO(
        success=False,
        data=None,
        error=ErrorDTO(code="INTERNAL_ERROR", message="内部错误"),
        message="request failed",
        trace_id=trace_id,
    )
    return JSONResponse(status_code=500, content=envelope.model_dump())
