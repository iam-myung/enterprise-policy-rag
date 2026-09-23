"""制度问答编排 AskPolicy（SPEC §2.2 / §9.2）。

编排：检索 → 重排 → 冲突判定 → 生成 → 引用校验。
约束：不裁决制度优先级；引用仅来自给定 evidence ids；禁止展示思维链。
可观测性：通过 TelemetryPort 记录事件/span/指标（SPEC §10.2），参数脱敏。
"""

from collections.abc import Callable, Mapping

from enterprise_policy_rag.application.ports.models import (
    ChatModelPort,
    ConflictDetectorPort,
    RerankerPort,
)
from enterprise_policy_rag.application.ports.telemetry import (
    TelemetryPort,
    noop_telemetry,
)
from enterprise_policy_rag.domain.citation_rules import (
    CitationValidationError,
    validate_citation_ids,
    validate_evidence_quote,
)
from enterprise_policy_rag.domain.confidence import compute_confidence
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.result import AnswerResult, AnswerStatus


class AskPolicy:
    """问答编排（SPEC §2.2 application.qa / §9.2）。"""

    def __init__(
        self,
        retriever: Callable[[str], tuple[Evidence, ...]],
        reranker: RerankerPort,
        conflict_detector: ConflictDetectorPort,
        chat_model: ChatModelPort,
        page_texts: Mapping[str, str],
        corpus_revision: str = "",
        evidence_threshold: float = 0.0,
        telemetry: TelemetryPort | None = None,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._conflict_detector = conflict_detector
        self._chat_model = chat_model
        self._page_texts = page_texts
        self._corpus_revision = corpus_revision
        self._evidence_threshold = evidence_threshold
        self._telemetry = telemetry if telemetry is not None else noop_telemetry()

    def ask(self, question: str) -> AnswerResult:
        with self._telemetry.start_span("retrieve"):
            candidates = self._retriever(question)
        return self.answer(question, candidates)

    def answer(
        self, question: str, candidates: tuple[Evidence, ...]
    ) -> AnswerResult:
        """给定候选证据作答（评测管线可复用，避免重复检索，SPEC §7.2）。"""
        with self._telemetry.start_span("qa.answer"):
            return self._answer(question, candidates)

    def _answer(
        self, question: str, candidates: tuple[Evidence, ...]
    ) -> AnswerResult:
        if not candidates:
            self._telemetry.record_event(
                "qa.no_evidence",
                (
                    ("corpus_revision", self._corpus_revision),
                    ("status", AnswerStatus.NO_EVIDENCE.value),
                    ("evidence_count", "0"),
                ),
            )
            self._telemetry.record_metric("qa.status.NO_EVIDENCE", 1.0)
            return AnswerResult(
                status=AnswerStatus.NO_EVIDENCE,
                answer="",
                citations=(),
                warnings=(),
                corpus_revision=self._corpus_revision,
                confidence=0.0,
            )

        if (
            self._evidence_threshold > 0.0
            and max(c.score for c in candidates) < self._evidence_threshold
        ):
            # 证据强度不足（SPEC §12 RAG_EVIDENCE_THRESHOLD）：拒答而非编造。
            self._telemetry.record_event(
                "qa.no_evidence",
                (
                    ("corpus_revision", self._corpus_revision),
                    ("status", AnswerStatus.NO_EVIDENCE.value),
                    ("evidence_count", str(len(candidates))),
                    ("reason", "EVIDENCE_BELOW_THRESHOLD"),
                ),
            )
            self._telemetry.record_metric("qa.status.NO_EVIDENCE", 1.0)
            return AnswerResult(
                status=AnswerStatus.NO_EVIDENCE,
                answer="",
                citations=(),
                warnings=("EVIDENCE_BELOW_THRESHOLD",),
                corpus_revision=self._corpus_revision,
                confidence=0.0,
            )

        with self._telemetry.start_span("rerank"):
            rerank_result = self._reranker.rerank(question, candidates)
        candidates = self._apply_rerank(candidates, rerank_result.evidence_ids)
        assessment = self._conflict_detector.detect(question, candidates)
        with self._telemetry.start_span("answer.generate"):
            model_answer = self._chat_model.generate(question, candidates)

        evidence_by_id = {c.evidence_id: c for c in candidates}

        if assessment.is_conflict:
            # CONFLICT：引用冲突检测器给出的两条互斥 claim 证据（SPEC §4.4 / §8.5），
            # 而非回答模型的 citation_ids；二者都必须通过原文子串校验。
            with self._telemetry.start_span("citation.validate"):
                self._validate_citations(assessment.evidence_ids, candidates)
            citations = tuple(
                evidence_by_id[citation_id]
                for citation_id in assessment.evidence_ids
            )
            status = AnswerStatus.CONFLICT
            answer = model_answer.conflict_note or ""
        else:
            with self._telemetry.start_span("citation.validate"):
                self._validate_citations(model_answer.citation_ids, candidates)
            citations = tuple(
                evidence_by_id[citation_id]
                for citation_id in model_answer.citation_ids
            )
            status = model_answer.status
            answer = model_answer.answer

        warnings = ("RERANKER_DEGRADED",) if rerank_result.degraded else ()

        self._telemetry.record_event(
            "qa.answered",
            (
                ("corpus_revision", self._corpus_revision),
                ("status", status.value),
                ("evidence_count", str(len(candidates))),
                ("citation_count", str(len(citations))),
                ("degraded", "true" if rerank_result.degraded else "false"),
            ),
        )
        self._telemetry.record_metric(f"qa.status.{status.value}", 1.0)
        if rerank_result.degraded:
            self._telemetry.record_metric("qa.degraded", 1.0)

        return AnswerResult(
            status=status,
            answer=answer,
            citations=citations,
            warnings=warnings,
            corpus_revision=self._corpus_revision,
            confidence=compute_confidence(
                status, citations, candidates, rerank_result.degraded
            ),
        )

    @staticmethod
    def _apply_rerank(
        candidates: tuple[Evidence, ...], ordered_ids: tuple[str, ...]
    ) -> tuple[Evidence, ...]:
        """按重排结果重排候选（SPEC §5.316），补齐遗漏候选以保证不丢。

        rerank 只能返回已给定 ID（子集可能缺失），此处既应用排序又补全，
        确保后续冲突判定/生成仍覆盖全部候选。
        """
        evidence_by_id = {c.evidence_id: c for c in candidates}
        seen: set[str] = set()
        ordered: list[Evidence] = []
        for eid in ordered_ids:
            evidence = evidence_by_id.get(eid)
            if evidence is not None and eid not in seen:
                ordered.append(evidence)
                seen.add(eid)
        for candidate in candidates:
            if candidate.evidence_id not in seen:
                ordered.append(candidate)
        return tuple(ordered)

    def _validate_citations(
        self, citation_ids: tuple[str, ...], candidates: tuple[Evidence, ...]
    ) -> None:
        """引用校验（SPEC §9.2）：未知 ID 拒绝 + quote 原文子串校验（含冲突路径）。"""
        given_ids = {c.evidence_id for c in candidates}
        validate_citation_ids(citation_ids, given_ids)

        evidence_by_id = {c.evidence_id: c for c in candidates}
        for citation_id in citation_ids:
            evidence = evidence_by_id[citation_id]
            page_text = self._page_texts.get(citation_id)
            if page_text is None:
                raise CitationValidationError(
                    f"无法校验引用的页文本: {citation_id}"
                )
            try:
                validate_evidence_quote(evidence, page_text)
            except ValueError as exc:
                raise CitationValidationError(
                    f"引用 quote 与页文本不一致: {citation_id}"
                ) from exc
