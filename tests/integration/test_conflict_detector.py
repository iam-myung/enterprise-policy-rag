"""QwenConflictDetector 集成测试（SPEC §5.317）。

回归守护：Provider 失败抛 ConflictDetectorError，且它是 AppError → 502
（上层 questions 端点可捕获并映射统一 Envelope）。
"""

import pytest

from enterprise_policy_rag.adapters.llm.conflict_detector import (
    ConflictDetectorError,
    QwenConflictDetector,
)
from enterprise_policy_rag.application.ports.models import (
    ConflictAssessmentDTO,
    ConflictReasonCode,
)
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.errors import AppError, ErrorCode


def _evidence(evidence_id: str) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        chunk_id=f"{evidence_id}-chunk",
        document_id=f"doc-{evidence_id}",
        title="制度",
        version="v1",
        page=1,
        char_start=0,
        char_end=1,
        quote="x",
        page_text_sha256="0" * 64,
        score=1.0,
    )


def _assessment() -> ConflictAssessmentDTO:
    return ConflictAssessmentDTO(
        is_conflict=True,
        claim_a="年假 15 天",
        claim_b="年假 10 天",
        evidence_ids=("e1", "e2"),
        reason_code=ConflictReasonCode.MUTUALLY_EXCLUSIVE_RULES,
    )


def test_conflict_detector_error_is_app_error() -> None:
    """ConflictDetectorError 继承 AppError → 502 LLM_PROVIDER_ERROR（QA 回归）。"""
    err = ConflictDetectorError("冲突判定失败")
    assert isinstance(err, AppError)
    assert err.code is ErrorCode.LLM_PROVIDER_ERROR
    assert err.code.http_status == 502


def test_detect_raises_conflict_detector_error_on_provider_failure() -> None:
    """Provider 抛异常 → detect 抛 ConflictDetectorError（AppError），不泄漏原始异常。"""
    candidates = (_evidence("e1"), _evidence("e2"))

    def provider(question, cands):
        raise RuntimeError("provider down")

    detector = QwenConflictDetector(provider)
    with pytest.raises(ConflictDetectorError):
        detector.detect("年假有多少天", candidates)
