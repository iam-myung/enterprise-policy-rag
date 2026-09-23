"""制度领域实体（SPEC §4.1）。

domain 纯净：仅依赖标准库。
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from enterprise_policy_rag.domain.value_objects import DateRange


class DocumentStatus(StrEnum):
    """文档状态（SPEC §4.2 状态机）。"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"


@dataclass
class PolicyDocument:
    """制度文档（SPEC §4.1）。不变量：expires_at 不得早于 effective_at。"""

    id: str
    title: str
    version: str
    effective_at: date | None
    expires_at: date | None
    scope: str
    source_kind: str
    status: DocumentStatus
    sha256: str
    page_count: int | None
    source_relpath: str | None = None

    def __post_init__(self) -> None:
        # 复用 DateRange 值对象校验「expires_at 不得早于 effective_at」不变量。
        DateRange(self.effective_at, self.expires_at)


@dataclass(frozen=True)
class ParsedPage:
    """规范页文本（SPEC §4.1）。页码从 1 开始。"""

    document_id: str
    page_number: int
    source_text: str
    source_text_sha256: str

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("page_number 从 1 开始")


@dataclass
class KnowledgeChunk:
    """知识切片（SPEC §4.1）。Phase 1 不跨页，text 为源文本字符区间切片。"""

    id: str
    document_id: str
    ordinal: int
    page: int
    char_start: int
    char_end: int
    text: str
    text_sha256: str
    token_count: int


@dataclass(frozen=True)
class CorpusSnapshot:
    """语料快照（SPEC §4.1）。发布后不可变。"""

    revision: str
    active_document_ids: tuple[str, ...]
    index_path: str
    created_at: datetime


@dataclass
class Evidence:
    """检索证据（SPEC §4.1）。quote 必须由已保存页文本按字符区间截取。"""

    evidence_id: str
    chunk_id: str
    document_id: str
    title: str
    version: str
    page: int
    char_start: int
    char_end: int
    quote: str
    page_text_sha256: str
    score: float
