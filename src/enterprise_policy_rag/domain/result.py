"""统一结果与 Envelope（SPEC §6.1）、回答状态（SPEC §4.3）。

domain 纯净：仅依赖标准库与 domain.errors。
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.errors import ErrorCode

T = TypeVar("T")


class AnswerStatus(StrEnum):
    """回答状态（SPEC §4.3）。"""

    ANSWERED = "ANSWERED"
    NO_EVIDENCE = "NO_EVIDENCE"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class AnswerResult:
    """问答结果（SPEC §4.1）。"""

    status: AnswerStatus
    answer: str
    citations: tuple[Evidence, ...]
    warnings: tuple[str, ...]
    corpus_revision: str
    confidence: float


# error.context 白名单字段（SPEC §6.1：context 只能包含白名单字段）。
CONTEXT_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"field_name", "document_id", "page", "reason", "detail"}
)

_SECRET_MARKERS = ("sk-", "api_key", "token", "secret", "password", "bearer ")
_MAX_CONTEXT_VALUE_LENGTH = 500


def _is_sensitive(value: object) -> bool:
    """判断 context 值是否含未脱敏内容：密钥/令牌/绝对路径/完整原文/堆栈。"""
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return True
    if "traceback" in lowered:
        return True
    if "\\" in value or ":/" in value or value.startswith("/"):
        return True
    return len(value) > _MAX_CONTEXT_VALUE_LENGTH


def validate_error_context(context: dict[str, Any]) -> None:
    """校验 error.context：key 必须在白名单内，value 必须已脱敏；违反抛 ValueError。"""
    for key in context:
        if key not in CONTEXT_ALLOWED_KEYS:
            raise ValueError(f"error.context 含非白名单字段: {key}")
    for value in context.values():
        if _is_sensitive(value):
            raise ValueError("error.context 含未脱敏内容（密钥/绝对路径/完整原文/堆栈）")


@dataclass
class ErrorDetail:
    """统一错误结构（SPEC §6.1 error 字段）。"""

    code: ErrorCode
    message: str
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_error_context(self.context)


@dataclass
class OperationEnvelope(Generic[T]):
    """统一响应 Envelope（SPEC §6.1），构造时校验成功/失败互斥。"""

    success: bool
    data: T | None
    error: ErrorDetail | None
    message: str
    trace_id: str

    def __post_init__(self) -> None:
        if self.success:
            if self.error is not None or self.data is None:
                raise ValueError("success=True 要求 data 非空且 error 为 None")
        else:
            if self.data is not None or self.error is None:
                raise ValueError("success=False 要求 data 为 None 且 error 非空")
