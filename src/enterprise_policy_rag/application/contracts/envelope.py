"""统一 Envelope 的 Pydantic DTO（SPEC §6.1）。

application 层序列化契约；供 interfaces 层映射 domain OperationEnvelope 到 JSON。
"""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDTO(BaseModel):
    """失败响应 error 字段（SPEC §6.1）。"""

    code: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class EnvelopeDTO(BaseModel):
    """统一响应 Envelope 的序列化 DTO（SPEC §6.1）。"""

    success: bool
    data: Any | None = None
    error: ErrorDTO | None = None
    message: str
    trace_id: str
