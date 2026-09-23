"""AI 模型 Ports（SPEC §5.316 / §5.317）。

RerankerPort / ConflictDetectorPort：只能引用已给定 evidence ID；
所有 Port 返回不可变 DTO。
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.result import AnswerStatus


@dataclass(frozen=True)
class RerankResultDTO:
    """重排结果（evidence_ids 排序后；degraded=True 表示已退化为 RRF）。"""

    evidence_ids: tuple[str, ...]
    degraded: bool


class RerankerPort(Protocol):
    """重排 Port（SPEC §5.316）：只能返回已给定 evidence ID。"""

    def rerank(
        self, question: str, candidates: tuple[Evidence, ...]
    ) -> RerankResultDTO: ...


class ConflictReasonCode(StrEnum):
    """冲突原因码（SPEC §4.4）。"""

    MUTUALLY_EXCLUSIVE_RULES = "MUTUALLY_EXCLUSIVE_RULES"
    APPLICABILITY_AMBIGUITY = "APPLICABILITY_AMBIGUITY"


@dataclass(frozen=True)
class ConflictAssessmentDTO:
    """冲突评估结果（SPEC §4.4 / §5.317）。"""

    is_conflict: bool
    claim_a: str | None
    claim_b: str | None
    evidence_ids: tuple[str, ...]
    reason_code: ConflictReasonCode | None


class ConflictDetectorPort(Protocol):
    """冲突判定 Port（SPEC §5.317）：只引用输入 evidence ids，不裁决优先级。"""

    def detect(
        self, question: str, candidates: tuple[Evidence, ...]
    ) -> ConflictAssessmentDTO: ...


@dataclass(frozen=True)
class ModelAnswerDTO:
    """回答模型结构化输出（SPEC §9.3）。"""

    status: AnswerStatus
    answer: str
    citation_ids: tuple[str, ...]
    conflict_note: str | None


class ChatModelPort(Protocol):
    """回答模型 Port（SPEC §5.318）：只能引用已给定 evidence ids。"""

    def generate(
        self, question: str, evidences: tuple[Evidence, ...]
    ) -> ModelAnswerDTO: ...
