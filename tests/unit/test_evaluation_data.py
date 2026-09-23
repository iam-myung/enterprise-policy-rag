"""Step 12-BUILD：评测集数据质量检查（SPEC §7.2 / §4.4）。"""

from pathlib import Path

from enterprise_policy_rag.interfaces.cli.evaluate import load_cases

_CASES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "evaluation"
    / "cases"
    / "phase1.jsonl"
)


def test_phase1_has_at_least_20_cases() -> None:
    cases = load_cases(_CASES_PATH)
    assert len(cases) >= 20


def test_phase1_has_at_least_3_conflict_cases() -> None:
    """SPEC §4.4：固定评测集须含至少 3 条人工标注的冲突边界样本。"""
    cases = load_cases(_CASES_PATH)
    conflict = [c for c in cases if c.conflict_expected]
    assert len(conflict) >= 3


def test_phase1_covers_answerable_and_unanswerable() -> None:
    cases = load_cases(_CASES_PATH)
    assert any(c.answerable for c in cases)
    assert any(not c.answerable for c in cases)


def test_gold_evidence_uses_stable_refs() -> None:
    """gold 用 document_ref + page + quote_contains，不用 evidence_id。"""
    cases = load_cases(_CASES_PATH)
    for case in cases:
        if not case.answerable:
            continue
        assert case.gold_evidence, f"answerable 样本 {case.id} 缺少 gold_evidence"
        for g in case.gold_evidence:
            assert g.document_ref
            assert g.page >= 1
            assert g.quote_contains


def test_conflict_cases_have_two_gold_evidence() -> None:
    """冲突样本须标注两份互斥 claim 的证据（SPEC §4.4 条件）。"""
    cases = load_cases(_CASES_PATH)
    for case in cases:
        if case.conflict_expected:
            assert len(case.gold_evidence) >= 2, f"冲突样本 {case.id} 需两组 gold"
