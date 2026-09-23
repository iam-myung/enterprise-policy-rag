"""评测 CLI 纯逻辑（SPEC §7.2）。

只定义命令逻辑与指标报告格式化；装配由 composition（Composition Root）完成，
本模块不 import composition。基线与目标必须同 corpus revision、同评测集版本、
同回答模型（由调用方保证）。可观测性实例由调用方（composition）注入。
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from enterprise_policy_rag.application.contracts.evaluations import (
    EvaluationCase,
    GoldEvidence,
    MetricReport,
)
from enterprise_policy_rag.application.evaluation.evaluate_rag import (
    EvaluateRag,
    EvaluationPipeline,
)
from enterprise_policy_rag.application.ports.telemetry import TelemetryPort


def load_cases(path: Path) -> tuple[EvaluationCase, ...]:
    """加载 phase1.jsonl 评测集（SPEC §7.2）。"""
    cases: list[EvaluationCase] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            gold = tuple(
                GoldEvidence(
                    document_ref=g["document_ref"],
                    page=g["page"],
                    quote_contains=g["quote_contains"],
                )
                for g in raw["gold_evidence"]
            )
            cases.append(
                EvaluationCase(
                    id=raw["id"],
                    question=raw["question"],
                    answerable=raw["answerable"],
                    conflict_expected=raw["conflict_expected"],
                    gold_evidence=gold,
                    reference_answer=raw.get("reference_answer"),
                    tags=tuple(raw.get("tags", [])),
                )
            )
    return tuple(cases)


def evaluate_scheme(
    cases: tuple[EvaluationCase, ...],
    pipeline: EvaluationPipeline,
    corpus_revision: str,
    scheme: str,
    telemetry: TelemetryPort | None = None,
) -> MetricReport:
    """运行单个方案评测。"""
    return EvaluateRag(
        cases, pipeline, corpus_revision, scheme, telemetry=telemetry
    ).run()


def _metric_dict(report: MetricReport) -> dict[str, object]:
    metrics: dict[str, object] = {}
    for m in report.metrics:
        if m.value is None:
            metrics[m.name] = f"NOT_APPLICABLE（{m.reason or '缺少字段'}）"
        else:
            metrics[m.name] = round(m.value, 4)
    return metrics


def format_report(baseline: MetricReport, target: MetricReport) -> str:
    """输出基线与目标方案对比报告（JSON）。"""
    payload = {
        "baseline": {
            "scheme": baseline.scheme,
            "corpus_revision": baseline.corpus_revision,
            "sample_count": baseline.sample_count,
            "degraded_count": baseline.degraded_count,
            "metrics": _metric_dict(baseline),
        },
        "target": {
            "scheme": target.scheme,
            "corpus_revision": target.corpus_revision,
            "sample_count": target.sample_count,
            "degraded_count": target.degraded_count,
            "metrics": _metric_dict(target),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def run(
    baseline: EvaluationPipeline,
    target: EvaluationPipeline,
    corpus_revision: str,
    argv: Sequence[str] | None = None,
    telemetry: TelemetryPort | None = None,
) -> int:
    """给定已装配的 baseline/target 管线，执行评测并输出报告。"""
    parser = argparse.ArgumentParser(description="RAG 评测")
    parser.add_argument("--cases", required=True, help="评测集 phase1.jsonl 路径")
    parser.add_argument(
        "--dataset-version", default="phase1.v1", help="评测集版本（写入报告）"
    )
    args = parser.parse_args(argv)

    cases = load_cases(Path(args.cases))
    if not cases:
        print("评测集为空，无法评测。", file=sys.stderr)
        return 2
    if not corpus_revision:
        print("无 active 语料，请先导入制度 PDF。", file=sys.stderr)
        return 2

    baseline_report = evaluate_scheme(
        cases, baseline, corpus_revision, "baseline", telemetry=telemetry
    )
    target_report = evaluate_scheme(
        cases, target, corpus_revision, "target", telemetry=telemetry
    )

    print(format_report(baseline_report, target_report))
    return 0
