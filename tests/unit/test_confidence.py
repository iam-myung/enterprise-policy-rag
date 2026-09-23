"""置信度纯函数单元测试（综合可信度 0~1）。

覆盖规则：NO_EVIDENCE/CONFLICT 定档、ANSWERED 检索强度、降级折扣、值域。
"""

from enterprise_policy_rag.domain.confidence import compute_confidence
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.result import AnswerStatus


def _ev(eid: str, score: float) -> Evidence:
    return Evidence(
        evidence_id=eid,
        chunk_id=eid,
        document_id="doc-1",
        title="制度",
        version="v1",
        page=1,
        char_start=0,
        char_end=5,
        quote="文本",
        page_text_sha256="0" * 64,
        score=score,
    )


def test_no_evidence_confidence_is_zero() -> None:
    assert compute_confidence(AnswerStatus.NO_EVIDENCE, (), (), False) == 0.0


def test_conflict_confidence_is_fixed() -> None:
    assert compute_confidence(AnswerStatus.CONFLICT, (), (), False) == 0.35


def test_answered_without_candidates_is_zero() -> None:
    assert compute_confidence(AnswerStatus.ANSWERED, (), (), False) == 0.0


def test_answered_high_discrimination_high_confidence() -> None:
    """分数差大 → 检索区分度高 → 置信度偏高。"""
    candidates = (_ev("e1", 1.0), _ev("e2", 0.01), _ev("e3", 0.01))
    citations = (_ev("e1", 1.0),)
    conf = compute_confidence(AnswerStatus.ANSWERED, citations, candidates, False)
    assert conf > 0.8


def test_answered_low_discrimination_moderate_confidence() -> None:
    """RRF 窄分数 → 区分度低 → 置信度中等（0.6~0.8）。"""
    candidates = (_ev("e1", 0.033), _ev("e2", 0.032), _ev("e3", 0.031))
    citations = (_ev("e1", 0.033),)
    conf = compute_confidence(AnswerStatus.ANSWERED, citations, candidates, False)
    assert 0.6 <= conf < 0.8


def test_degraded_applies_discount() -> None:
    """degraded 时整体 ×0.8。"""
    candidates = (_ev("e1", 1.0), _ev("e2", 0.01))
    citations = (_ev("e1", 1.0),)
    normal = compute_confidence(AnswerStatus.ANSWERED, citations, candidates, False)
    degraded = compute_confidence(AnswerStatus.ANSWERED, citations, candidates, True)
    assert degraded == round(normal * 0.8, 4)


def test_confidence_within_unit_range() -> None:
    """置信度始终落在 [0, 1]。"""
    candidates = (_ev("e1", 1.0), _ev("e2", 0.5))
    citations = (_ev("e1", 1.0),)
    for degraded in (False, True):
        conf = compute_confidence(
            AnswerStatus.ANSWERED, citations, candidates, degraded
        )
        assert 0.0 <= conf <= 1.0
