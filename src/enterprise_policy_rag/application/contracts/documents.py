"""文档相关 DTO（SPEC §8.3 DocumentSummaryDTO）。"""

from dataclasses import dataclass
from datetime import date

from enterprise_policy_rag.domain.entities import DocumentStatus


@dataclass
class DocumentSummaryDTO:
    """文档导入摘要（SPEC §8.3）。"""

    id: str
    title: str
    version: str
    effective_at: date | None
    expires_at: date | None
    scope: str
    status: DocumentStatus
    page_count: int | None
    corpus_revision: str
