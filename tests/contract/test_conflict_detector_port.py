"""Step 8-RED：ConflictDetectorPort 契约测试（SPEC §5.317 / §4.4）。

验收点：
② ConflictDetectorPort：返回 ConflictAssessmentDTO 五字段，
   reason_code ∈ {MUTUALLY_EXCLUSIVE_RULES, APPLICABILITY_AMBIGUITY}；只引用输入 evidence ids。
"""

from dataclasses import FrozenInstanceError

import pytest

from enterprise_policy_rag.application.ports.models import (
    ConflictAssessmentDTO,
    ConflictDetectorPort,
    ConflictReasonCode,
)


def test_reason_code_enum_values() -> None:
    """reason_code 仅允许两个枚举值（SPEC §4.4）。"""
    assert {r.value for r in ConflictReasonCode} == {
        "MUTUALLY_EXCLUSIVE_RULES",
        "APPLICABILITY_AMBIGUITY",
    }


def test_conflict_assessment_fields() -> None:
    """ConflictAssessmentDTO 字段：is_conflict/claim_a/claim_b/evidence_ids/reason_code。"""
    dto = ConflictAssessmentDTO(
        is_conflict=True,
        claim_a="年假 15 天",
        claim_b="年假 10 天",
        evidence_ids=("e1", "e2"),
        reason_code=ConflictReasonCode.MUTUALLY_EXCLUSIVE_RULES,
    )
    assert dto.is_conflict is True
    assert dto.claim_a == "年假 15 天"
    assert dto.claim_b == "年假 10 天"
    assert dto.evidence_ids == ("e1", "e2")
    assert dto.reason_code is ConflictReasonCode.MUTUALLY_EXCLUSIVE_RULES


def test_conflict_assessment_is_immutable() -> None:
    """冲突评估结果不可变。"""
    dto = ConflictAssessmentDTO(
        is_conflict=False, claim_a=None, claim_b=None, evidence_ids=(), reason_code=None
    )
    with pytest.raises(FrozenInstanceError):
        dto.is_conflict = True  # type: ignore[misc]


def test_conflict_detector_port_declares_detect() -> None:
    """ConflictDetectorPort 协议必须声明 detect 方法（SPEC §5.317）。"""
    assert hasattr(ConflictDetectorPort, "detect")
