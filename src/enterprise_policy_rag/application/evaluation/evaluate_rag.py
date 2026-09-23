"""RAG 评测编排与指标计算（SPEC §7.2）。

EvaluateRag 对每个样本运行管线（baseline / target），计算确定性指标：
Recall@K、引用正确率、忠实度、答案正确率、拒答率、冲突准确率、P95 延迟、退化计数。
无法计算的指标返回 NOT_APPLICABLE（value=None + reason），不得记 0 或 PASS。
可观测性：通过 TelemetryPort 记录评测汇总事件（corpus_revision / degraded_count）。
"""

from typing import Protocol

import jieba  # type: ignore[import-untyped]

from enterprise_policy_rag.application.contracts.evaluations import (
    EvaluationCase,
    MetricReport,
    MetricResult,
    PipelineResult,
)
from enterprise_policy_rag.application.ports.telemetry import (
    TelemetryPort,
    noop_telemetry,
)


class EvaluationPipeline(Protocol):
    """评测管线（baseline / target 共用抽象）：输入问题，输出运行结果。"""

    def run(self, question: str) -> PipelineResult: ...


class EvaluateRag:
    """评测编排（SPEC §2.2 application.evaluation）。不修改生产索引。"""

    def __init__(
        self,
        cases: tuple[EvaluationCase, ...],
        pipeline: EvaluationPipeline,
        corpus_revision: str,
        scheme: str,
        telemetry: TelemetryPort | None = None,
    ) -> None:
        self._cases = cases
        self._pipeline = pipeline
        self._corpus_revision = corpus_revision
        self._scheme = scheme
        self._telemetry = telemetry if telemetry is not None else noop_telemetry()

    def run(self) -> MetricReport:
        results: dict[str, PipelineResult] = {}
        for case in self._cases:
            results[case.id] = self._pipeline.run(case.question)
        report = compute_metrics(
            self._scheme, self._corpus_revision, self._cases, results
        )
        self._telemetry.record_event(
            "evaluate.completed",
            (
                ("scheme", self._scheme),
                ("corpus_revision", self._corpus_revision),
                ("sample_count", str(len(self._cases))),
                ("degraded_count", str(report.degraded_count)),
            ),
        )
        self._telemetry.record_metric("evaluate.sample_count", float(len(self._cases)))
        return report


def compute_metrics(
    scheme: str,
    corpus_revision: str,
    cases: tuple[EvaluationCase, ...],
    results: dict[str, PipelineResult],
) -> MetricReport:
    """计算全部指标（SPEC §7.2）。results: case_id -> PipelineResult。"""
    metrics = (
        _recall_at_k(cases, results),
        _citation_correctness(cases, results),
        _faithfulness(cases, results),
        _answer_correctness(cases, results),
        _answer_accuracy(cases, results),
        _refusal_accuracy(cases, results),
        _conflict_accuracy(cases, results),
        _latency_p95(results),
    )
    degraded_count = sum(1 for r in results.values() if r.degraded)
    return MetricReport(
        scheme=scheme,
        corpus_revision=corpus_revision,
        metrics=metrics,
        degraded_count=degraded_count,
        sample_count=len(cases),
    )


def _recall_at_k(
    cases: tuple[EvaluationCase, ...], results: dict[str, PipelineResult]
) -> MetricResult:
    """Recall@K：gold_evidence 的 (document_ref, page) 是否进入候选（answerable=true）。"""
    applicable = [c for c in cases if c.answerable]
    if not applicable:
        return MetricResult("recall_at_k", None, "无 answerable=true 样本")
    hit = 0
    for case in applicable:
        candidate_pages = {(e.title, e.page) for e in results[case.id].candidates}
        if any((g.document_ref, g.page) in candidate_pages for g in case.gold_evidence):
            hit += 1
    return MetricResult("recall_at_k", hit / len(applicable))


def _citation_correctness(
    cases: tuple[EvaluationCase, ...], results: dict[str, PipelineResult]
) -> MetricResult:
    """引用正确率：引用 quote 是否含 gold quote_contains（ANSWERED/CONFLICT）。"""
    applicable = [
        c for c in cases if results[c.id].status in ("ANSWERED", "CONFLICT")
    ]
    if not applicable:
        return MetricResult("citation_correctness", None, "无 ANSWERED/CONFLICT 样本")
    hit = 0
    for case in applicable:
        quotes = [e.quote for e in results[case.id].citations]
        if any(g.quote_contains in q for g in case.gold_evidence for q in quotes):
            hit += 1
    return MetricResult("citation_correctness", hit / len(applicable))


def _faithfulness(
    cases: tuple[EvaluationCase, ...], results: dict[str, PipelineResult]
) -> MetricResult:
    """轻量忠实度（SPEC §7.2 Faithfulness，Phase 1 不引入 RAGAS）。

    适用样本：仅 ``ANSWERED``（与 SPEC §7.2 指标表一致；不含 CONFLICT）。
    确定性算法：jieba 分词 answer，过滤单字/标点，计算每个词在 citations.quote
    拼接串中作为子串出现的比例（越接近 1 表示 answer 陈述越被引用原文支持）。
    局限：仅做词级子串覆盖，不做语义蕴含判断。
    """
    applicable = [c for c in cases if results[c.id].status == "ANSWERED"]
    if not applicable:
        return MetricResult("faithfulness", None, "无 ANSWERED 样本")
    ratios: list[float] = []
    for case in applicable:
        r = results[case.id]
        answer = r.answer or ""
        quotes = "\n".join(e.quote for e in r.citations)
        if not answer.strip():
            continue
        words = [w for w in jieba.lcut(answer) if len(w.strip()) > 1]
        if not words:
            continue
        hits = sum(1 for w in words if w in quotes)
        ratios.append(hits / len(words))
    if not ratios:
        return MetricResult("faithfulness", None, "无可计算的 answer 文本")
    return MetricResult("faithfulness", sum(ratios) / len(ratios))


def _answer_correctness(
    cases: tuple[EvaluationCase, ...], results: dict[str, PipelineResult]
) -> MetricResult:
    """答案正确率：与人工参考答案子串匹配（仅有人工参考答案的样本）。"""
    applicable = [c for c in cases if c.reference_answer is not None]
    if not applicable:
        return MetricResult("answer_correctness", None, "无 reference_answer 标注")
    hit = 0
    for case in applicable:
        ref = case.reference_answer
        answer = results[case.id].answer
        if ref and (ref in answer or answer in ref):
            hit += 1
    return MetricResult("answer_correctness", hit / len(applicable))


def _answer_accuracy(
    cases: tuple[EvaluationCase, ...], results: dict[str, PipelineResult]
) -> MetricResult:
    """对有答案问题正确回答（ANSWERED/CONFLICT），不误拒。"""
    applicable = [c for c in cases if c.answerable]
    if not applicable:
        return MetricResult("answer_accuracy", None, "无 answerable=true 样本")
    hit = sum(
        1 for c in applicable if results[c.id].status in ("ANSWERED", "CONFLICT")
    )
    return MetricResult("answer_accuracy", hit / len(applicable))


def _refusal_accuracy(
    cases: tuple[EvaluationCase, ...], results: dict[str, PipelineResult]
) -> MetricResult:
    """对无答案问题正确拒答（NO_EVIDENCE），不编造。"""
    applicable = [c for c in cases if not c.answerable]
    if not applicable:
        return MetricResult("refusal_accuracy", None, "无 answerable=false 样本")
    hit = sum(1 for c in applicable if results[c.id].status == "NO_EVIDENCE")
    return MetricResult("refusal_accuracy", hit / len(applicable))


def _conflict_accuracy(
    cases: tuple[EvaluationCase, ...], results: dict[str, PipelineResult]
) -> MetricResult:
    """冲突准确率：conflict_expected 与实际 CONFLICT 状态一致（不漏报、不误报）。"""
    conflict_cases = [c for c in cases if c.conflict_expected]
    if not conflict_cases:
        return MetricResult("conflict_accuracy", None, "无 conflict_expected=true 样本")
    hit = 0
    for case in cases:
        is_conflict = results[case.id].status == "CONFLICT"
        if is_conflict == case.conflict_expected:
            hit += 1
    return MetricResult("conflict_accuracy", hit / len(cases))


def _latency_p95(results: dict[str, PipelineResult]) -> MetricResult:
    """P95 延迟（毫秒）。"""
    values = sorted(r.latency_ms for r in results.values())
    if not values:
        return MetricResult("latency_p95_ms", None, "无样本")
    idx = (len(values) - 1) * 0.95
    lo = int(idx)
    hi = min(lo + 1, len(values) - 1)
    value = values[lo] + (values[hi] - values[lo]) * (idx - lo)
    return MetricResult("latency_p95_ms", value)
