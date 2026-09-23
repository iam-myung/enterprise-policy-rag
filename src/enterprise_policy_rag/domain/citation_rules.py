"""引用有效性规则（SPEC §4.1 Evidence 不变量 / §6.2 CITATION_VALIDATION_FAILED）。

domain 纯净：仅依赖标准库与 domain.entities。
"""

from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.errors import AppError, ErrorCode


class CitationValidationError(AppError):
    """引用校验失败（未知 ID / 伪造引用）→ 502 CITATION_VALIDATION_FAILED。"""

    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.CITATION_VALIDATION_FAILED, message)


def validate_evidence_quote(evidence: Evidence, page_text: str) -> None:
    """校验 evidence.quote 必须由已保存页文本按字符区间截取。"""
    if evidence.quote != page_text[evidence.char_start : evidence.char_end]:
        raise ValueError("evidence.quote 必须等于 page_text[char_start:char_end]")


def validate_citation_ids(
    citation_ids: tuple[str, ...], given_ids: set[str]
) -> None:
    """校验 citation_ids 均为给定 evidence ids 子集；未知 ID 抛 CitationValidationError。"""
    for citation_id in citation_ids:
        if citation_id not in given_ids:
            raise CitationValidationError(
                f"引用含未知 evidence ID: {citation_id}"
            )
