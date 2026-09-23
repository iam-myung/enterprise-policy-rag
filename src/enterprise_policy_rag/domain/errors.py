"""ErrorCode 与错误分类（SPEC §6.2）。

domain 纯净：仅依赖标准库。
"""

from enum import StrEnum


class ErrorCategory(StrEnum):
    """错误分类（SPEC §6.2 分类列）。"""

    INPUT = "INPUT"
    FILE = "FILE"
    DOCUMENT = "DOCUMENT"
    PARSE = "PARSE"
    INDEX = "INDEX"
    PROVIDER = "PROVIDER"
    CITATION = "CITATION"
    SYSTEM = "SYSTEM"


class ErrorCode(StrEnum):
    """统一错误码（SPEC §6.2），携带 http_status 与分类。"""

    # 实例属性（__new__ 中动态赋值），显式声明以通过 mypy 严格检查。
    http_status: int
    category: ErrorCategory

    VALIDATION_ERROR = ("VALIDATION_ERROR", 422, ErrorCategory.INPUT)
    UNSUPPORTED_FILE_TYPE = ("UNSUPPORTED_FILE_TYPE", 415, ErrorCategory.FILE)
    FILE_TOO_LARGE = ("FILE_TOO_LARGE", 413, ErrorCategory.FILE)
    DOCUMENT_METADATA_REQUIRED = ("DOCUMENT_METADATA_REQUIRED", 422, ErrorCategory.DOCUMENT)
    DUPLICATE_DOCUMENT = ("DUPLICATE_DOCUMENT", 409, ErrorCategory.DOCUMENT)
    DOCUMENT_NOT_FOUND = ("DOCUMENT_NOT_FOUND", 404, ErrorCategory.DOCUMENT)
    DOCUMENT_NOT_READY = ("DOCUMENT_NOT_READY", 409, ErrorCategory.DOCUMENT)
    DOCUMENT_PARSE_FAILED = ("DOCUMENT_PARSE_FAILED", 422, ErrorCategory.PARSE)
    INDEX_BUILD_FAILED = ("INDEX_BUILD_FAILED", 500, ErrorCategory.INDEX)
    EMBEDDING_PROVIDER_ERROR = ("EMBEDDING_PROVIDER_ERROR", 502, ErrorCategory.PROVIDER)
    RERANKER_PROVIDER_ERROR = ("RERANKER_PROVIDER_ERROR", 502, ErrorCategory.PROVIDER)
    LLM_PROVIDER_ERROR = ("LLM_PROVIDER_ERROR", 502, ErrorCategory.PROVIDER)
    CITATION_VALIDATION_FAILED = ("CITATION_VALIDATION_FAILED", 502, ErrorCategory.CITATION)
    INTERNAL_ERROR = ("INTERNAL_ERROR", 500, ErrorCategory.SYSTEM)

    def __new__(
        cls, value: str, http_status: int, category: ErrorCategory
    ) -> "ErrorCode":
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.http_status = http_status
        obj.category = category
        return obj


class AppError(ValueError):
    """携带 ErrorCode 的应用异常（SPEC §6.1：原始异常仅进日志，API 只接收标准错误码）。

    继承 ValueError 以保持既有 `pytest.raises(ValueError)` 兼容。
    """

    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class DocumentNotFoundError(AppError):
    """文档不存在 → 404 DOCUMENT_NOT_FOUND（SPEC §8.6）。"""

    def __init__(self) -> None:
        super().__init__(ErrorCode.DOCUMENT_NOT_FOUND, "文档不存在")


class DocumentNotReadyError(AppError):
    """文档未就绪 → 409 DOCUMENT_NOT_READY（SPEC §8.6）。"""

    def __init__(self) -> None:
        super().__init__(ErrorCode.DOCUMENT_NOT_READY, "文档未就绪")


class PageOutOfRangeError(AppError):
    """页码越界 → 422 VALIDATION_ERROR（SPEC §8.6 的 422 分支）。"""

    def __init__(self) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, "页码越界")
