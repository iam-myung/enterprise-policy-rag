"""评测 DTO（SPEC §4.1 GoldEvidence/EvaluationCase / §7.2 指标）。"""

from dataclasses import dataclass

from enterprise_policy_rag.domain.entities import Evidence


@dataclass(frozen=True)
class GoldEvidence:
    """金标证据（SPEC §4.1）：用稳定的文档引用 + 页码 + 原文短语，不用 evidence_id。"""

    document_ref: str
    page: int
    quote_contains: str


@dataclass(frozen=True)
class EvaluationCase:
    """评测样本（SPEC §4.1）。"""

    id: str
    question: str
    answerable: bool
    conflict_expected: bool
    gold_evidence: tuple[GoldEvidence, ...]
    reference_answer: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineResult:
    """单条样本的管线运行结果（baseline / target 共用）。"""

    status: str
    answer: str
    citations: tuple[Evidence, ...]
    candidates: tuple[Evidence, ...]
    latency_ms: float
    degraded: bool


@dataclass(frozen=True)
class MetricResult:
    """单项指标结果；value 为 None 表示 NOT_APPLICABLE（SPEC §7.2）。"""

    name: str
    value: float | None
    reason: str | None = None


@dataclass(frozen=True)
class MetricReport:
    """单方案（baseline / target）的指标报告（SPEC §7.2）。"""

    scheme: str
    corpus_revision: str
    metrics: tuple[MetricResult, ...]
    degraded_count: int
    sample_count: int
