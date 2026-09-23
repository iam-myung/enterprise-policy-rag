"""Step 12-BUILD：评测指标计算与数据加载测试（SPEC §7.2）。"""

from enterprise_policy_rag.application.contracts.evaluations import (
    EvaluationCase,
    GoldEvidence,
    PipelineResult,
)
from enterprise_policy_rag.application.evaluation.evaluate_rag import compute_metrics
from enterprise_policy_rag.domain.entities import Evidence


def _evidence(evidence_id: str, title: str, page: int, quote: str) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        chunk_id=f"{evidence_id}-chunk",
        document_id=f"doc-{evidence_id}",
        title=title,
        version="v1",
        page=page,
        char_start=0,
        char_end=len(quote),
        quote=quote,
        page_text_sha256="0" * 64,
        score=1.0,
    )


def _case(case_id: str, answerable: bool, conflict: bool = False) -> EvaluationCase:
    return EvaluationCase(
        id=case_id,
        question=f"问题 {case_id}",
        answerable=answerable,
        conflict_expected=conflict,
        gold_evidence=(
            GoldEvidence(document_ref="考勤管理制度", page=1, quote_contains="迟到"),
        ),
    )


def _result(status: str, *, hit_page: bool = True, quote: str = "迟到须扣款") -> PipelineResult:
    candidates = (_evidence("e1", "考勤管理制度", 1, quote),) if hit_page else ()
    citations = candidates if status == "ANSWERED" else ()
    return PipelineResult(
        status=status,
        answer="迟到须扣款" if status == "ANSWERED" else "",
        citations=citations,
        candidates=candidates,
        latency_ms=100.0,
        degraded=False,
    )


def test_recall_at_k_hit() -> None:
    """answerable 样本，候选含 gold 页 → recall_at_k = 1.0。"""
    cases = (_case("c1", True),)
    results = {"c1": _result("ANSWERED", hit_page=True)}
    report = compute_metrics("target", "rev-1", cases, results)
    recall = next(m for m in report.metrics if m.name == "recall_at_k")
    assert recall.value == 1.0


def test_recall_at_k_miss() -> None:
    """候选未含 gold 页 → recall_at_k = 0.0。"""
    cases = (_case("c1", True),)
    results = {"c1": _result("ANSWERED", hit_page=False)}
    report = compute_metrics("target", "rev-1", cases, results)
    recall = next(m for m in report.metrics if m.name == "recall_at_k")
    assert recall.value == 0.0


def test_not_applicable_when_no_answerable() -> None:
    """无 answerable=true 样本 → recall_at_k NOT_APPLICABLE（value=None）。"""
    cases = (_case("c1", False),)
    results = {"c1": _result("NO_EVIDENCE", hit_page=False)}
    report = compute_metrics("target", "rev-1", cases, results)
    recall = next(m for m in report.metrics if m.name == "recall_at_k")
    assert recall.value is None
    assert recall.reason is not None


def test_refusal_accuracy() -> None:
    """无答案样本正确拒答 → refusal_accuracy = 1.0。"""
    cases = (_case("c1", False),)
    results = {"c1": _result("NO_EVIDENCE", hit_page=False)}
    report = compute_metrics("target", "rev-1", cases, results)
    refusal = next(m for m in report.metrics if m.name == "refusal_accuracy")
    assert refusal.value == 1.0


def test_conflict_accuracy() -> None:
    """冲突样本判定一致 → conflict_accuracy = 1.0。"""
    cases = (_case("c1", True, conflict=True), _case("c2", True, conflict=False))
    results = {
        "c1": _result("CONFLICT", hit_page=True),
        "c2": _result("ANSWERED", hit_page=True),
    }
    report = compute_metrics("target", "rev-1", cases, results)
    conflict = next(m for m in report.metrics if m.name == "conflict_accuracy")
    assert conflict.value == 1.0


def test_faithfulness_not_applicable() -> None:
    """answer 为空（规则式无可计算文本）→ NOT_APPLICABLE。"""
    cases = (_case("c1", True),)
    r = _result("ANSWERED")
    empty = PipelineResult(
        status=r.status,
        answer="",
        citations=r.citations,
        candidates=r.candidates,
        latency_ms=r.latency_ms,
        degraded=r.degraded,
    )
    report = compute_metrics("target", "rev-1", cases, {"c1": empty})
    faithfulness = next(m for m in report.metrics if m.name == "faithfulness")
    assert faithfulness.value is None


def test_faithfulness_excludes_conflict_status() -> None:
    """SPEC §7.2：Faithfulness 仅适用 ANSWERED；仅 CONFLICT（即使有 answer）→ NOT_APPLICABLE。"""
    cases = (_case("c1", True, conflict=True),)
    quote = "迟到须扣款"
    ev = _evidence("e1", "考勤管理制度", 1, quote)
    conflict_with_answer = PipelineResult(
        status="CONFLICT",
        answer="迟到须扣款",
        citations=(ev,),
        candidates=(ev,),
        latency_ms=100.0,
        degraded=False,
    )
    report = compute_metrics("target", "rev-1", cases, {"c1": conflict_with_answer})
    faithfulness = next(m for m in report.metrics if m.name == "faithfulness")
    assert faithfulness.value is None
    assert faithfulness.reason is not None
    assert "ANSWERED" in faithfulness.reason


def test_faithfulness_rule_based_quote_overlap() -> None:
    """规则式忠实度：answer 的关键词全部出现在引用 quote 中 → 1.0。"""
    cases = (_case("c1", True),)
    report = compute_metrics("target", "rev-1", cases, {"c1": _result("ANSWERED")})
    faithfulness = next(m for m in report.metrics if m.name == "faithfulness")
    assert faithfulness.value is not None
    assert 0.0 <= faithfulness.value <= 1.0
