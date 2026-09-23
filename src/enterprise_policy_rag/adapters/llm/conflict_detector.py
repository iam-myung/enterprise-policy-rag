"""冲突判定适配器（SPEC §4.4 / §5.317）。

实现 ConflictDetectorPort：调用 Provider 判断语义互斥。
约束：Detector 超时/非法输出 → 抛 ConflictDetectorError（上层映射 Provider 失败 Envelope），
不得继续给确定性结论；不裁决制度优先级（只返回互斥 claim 与 reason_code）。
"""

from collections.abc import Callable

from enterprise_policy_rag.application.ports.models import (
    ConflictAssessmentDTO,
)
from enterprise_policy_rag.domain.conflict_rules import conflict_eligible
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.errors import AppError, ErrorCode


class ConflictDetectorError(AppError):
    """冲突判定 Provider 失败（超时 / 非法输出）→ 502 LLM_PROVIDER_ERROR。"""

    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.LLM_PROVIDER_ERROR, message)


class QwenConflictDetector:
    """Qwen 冲突判定适配器。

    provider：可调用，输入 (question, candidates) 返回 ConflictAssessmentDTO。
    """

    def __init__(
        self,
        provider: Callable[
            [str, tuple[Evidence, ...]], ConflictAssessmentDTO
        ],
        superseded_pairs: frozenset[tuple[str, str]] = frozenset(),
    ) -> None:
        self._provider = provider
        self._superseded_pairs = superseded_pairs

    def detect(
        self, question: str, candidates: tuple[Evidence, ...]
    ) -> ConflictAssessmentDTO:
        # §4.4 确定性前置条件（条件1 多制度 + 条件3 完整性 + 条件4 版本取代）：
        # 不满足时直接判「无冲突」，不调用 Provider（避免单制度/弱证据被误判为冲突）。
        if not conflict_eligible(candidates, self._superseded_pairs):
            return ConflictAssessmentDTO(
                is_conflict=False,
                claim_a=None,
                claim_b=None,
                evidence_ids=(),
                reason_code=None,
            )
        try:
            assessment = self._provider(question, candidates)
        except Exception as exc:
            raise ConflictDetectorError("冲突判定 Provider 失败") from exc
        self._validate(assessment, candidates)
        return assessment

    def _validate(
        self, assessment: ConflictAssessmentDTO, candidates: tuple[Evidence, ...]
    ) -> None:
        given_ids = {c.evidence_id for c in candidates}
        if not set(assessment.evidence_ids).issubset(given_ids):
            raise ConflictDetectorError("evidence_ids 含未知 ID")
        if assessment.is_conflict and assessment.reason_code is None:
            raise ConflictDetectorError("冲突但缺 reason_code")
