"""Step 9-RED：AskPolicy 三路径与引用校验契约测试（SPEC §4.3 / §8.5 / §9.2 / §9.3）。

验收点①②：
① AskPolicy 三路径：ANSWERED（引用非空）/NO_EVIDENCE（不得含推测答案）/
   CONFLICT（满足 4.4 且引用互斥 claim 证据）。
② 引用校验：模型返回未知 ID 或伪造引用 → CitationValidationError（上层映射
   CITATION_VALIDATION_FAILED）；冲突路径同样须通过原文子串校验。

所有 provider 均为 fake（不调用真实 LLM/网络）。
"""

import pytest

from enterprise_policy_rag.application.ports.models import (
    ConflictAssessmentDTO,
    ConflictReasonCode,
    ModelAnswerDTO,
    RerankResultDTO,
)
from enterprise_policy_rag.application.qa.ask_policy import AskPolicy
from enterprise_policy_rag.domain.citation_rules import CitationValidationError
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.result import AnswerStatus

PAGE_TEXT = "员工年假为每年十五天，须提前申请。"


def _evidence(evidence_id: str, doc_id: str, score: float = 1.0) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        chunk_id=f"{evidence_id}-chunk",
        document_id=doc_id,
        title="年假制度",
        version="v1",
        page=1,
        char_start=0,
        char_end=len(PAGE_TEXT),
        quote=PAGE_TEXT,
        page_text_sha256="0" * 64,
        score=score,
    )


class _FakeReranker:
    def rerank(self, question, candidates):
        return RerankResultDTO(
            evidence_ids=tuple(c.evidence_id for c in candidates), degraded=False
        )


class _FakeConflictDetector:
    def __init__(self, assessment: ConflictAssessmentDTO):
        self._assessment = assessment

    def detect(self, question, candidates):
        return self._assessment


class _FakeChatModel:
    def __init__(self, answer: ModelAnswerDTO):
        self._answer = answer

    def generate(self, question, evidences):
        return self._answer


def _no_conflict() -> ConflictAssessmentDTO:
    return ConflictAssessmentDTO(
        is_conflict=False,
        claim_a=None,
        claim_b=None,
        evidence_ids=(),
        reason_code=None,
    )


def _make_policy(
    retriever,
    conflict_detector,
    chat_model,
    page_texts=None,
    reranker=None,
    evidence_threshold=0.0,
):
    return AskPolicy(
        retriever=retriever,
        reranker=reranker or _FakeReranker(),
        conflict_detector=conflict_detector,
        chat_model=chat_model,
        page_texts=page_texts or {},
        evidence_threshold=evidence_threshold,
    )


def test_answered_path_returns_non_empty_citations() -> None:
    """① ANSWERED：有证据且模型给 ANSWERED → 引用非空。"""
    e1 = _evidence("e1", "d1")
    e2 = _evidence("e2", "d2")
    chat = _FakeChatModel(
        ModelAnswerDTO(
            status=AnswerStatus.ANSWERED,
            answer="年假为十五天",
            citation_ids=("e1",),
            conflict_note=None,
        )
    )
    policy = _make_policy(
        retriever=lambda q: (e1, e2),
        conflict_detector=_FakeConflictDetector(_no_conflict()),
        chat_model=chat,
        page_texts={"e1": PAGE_TEXT},
    )
    result = policy.ask("年假有多少天")
    assert result.status is AnswerStatus.ANSWERED
    assert len(result.citations) > 0


def test_no_evidence_path_has_no_speculative_answer() -> None:
    """① NO_EVIDENCE：无证据 → 不得含推测性答案（answer 为空或边界提示）。"""
    policy = _make_policy(
        retriever=lambda q: (),
        conflict_detector=_FakeConflictDetector(_no_conflict()),
        chat_model=_FakeChatModel(
            ModelAnswerDTO(
                status=AnswerStatus.NO_EVIDENCE,
                answer="",
                citation_ids=(),
                conflict_note=None,
            )
        ),
    )
    result = policy.ask("年假有多少天")
    assert result.status is AnswerStatus.NO_EVIDENCE
    # 不得给出制度结论
    assert "十五天" not in result.answer


def test_conflict_path_cites_mutually_exclusive_claims() -> None:
    """① CONFLICT：冲突判定成立 → 引用两条互斥 claim 的证据。"""
    e1 = _evidence("e1", "d1")
    e2 = _evidence("e2", "d2")
    conflict = ConflictAssessmentDTO(
        is_conflict=True,
        claim_a="年假 15 天",
        claim_b="年假 10 天",
        evidence_ids=("e1", "e2"),
        reason_code=ConflictReasonCode.MUTUALLY_EXCLUSIVE_RULES,
    )
    policy = _make_policy(
        retriever=lambda q: (e1, e2),
        conflict_detector=_FakeConflictDetector(conflict),
        chat_model=_FakeChatModel(
            ModelAnswerDTO(
                status=AnswerStatus.CONFLICT,
                answer="",
                citation_ids=("e1", "e2"),
                conflict_note="两份制度对年假天数规定不一致",
            )
        ),
        page_texts={"e1": PAGE_TEXT, "e2": PAGE_TEXT},
    )
    result = policy.ask("年假有多少天")
    assert result.status is AnswerStatus.CONFLICT
    assert {c.evidence_id for c in result.citations} == {"e1", "e2"}


def test_unknown_citation_id_raises() -> None:
    """② 引用校验：模型返回未知 ID → CitationValidationError。"""
    e1 = _evidence("e1", "d1")
    policy = _make_policy(
        retriever=lambda q: (e1,),
        conflict_detector=_FakeConflictDetector(_no_conflict()),
        chat_model=_FakeChatModel(
            ModelAnswerDTO(
                status=AnswerStatus.ANSWERED,
                answer="年假为十五天",
                citation_ids=("e99",),  # 未知 ID
                conflict_note=None,
            )
        ),
        page_texts={"e1": PAGE_TEXT},
    )
    with pytest.raises(CitationValidationError):
        policy.ask("年假有多少天")


def test_conflict_path_rejects_forged_quote() -> None:
    """② 冲突路径：quote 伪造（非页文本子串）→ CitationValidationError。"""
    e1 = _evidence("e1", "d1")
    forged = _evidence("e2", "d2")
    forged.quote = "模型编造的原文"  # 与页文本不一致
    conflict = ConflictAssessmentDTO(
        is_conflict=True,
        claim_a="年假 15 天",
        claim_b="年假 10 天",
        evidence_ids=("e1", "e2"),
        reason_code=ConflictReasonCode.MUTUALLY_EXCLUSIVE_RULES,
    )
    policy = _make_policy(
        retriever=lambda q: (e1, forged),
        conflict_detector=_FakeConflictDetector(conflict),
        chat_model=_FakeChatModel(
            ModelAnswerDTO(
                status=AnswerStatus.CONFLICT,
                answer="",
                citation_ids=("e1", "e2"),
                conflict_note="两份制度对年假天数规定不一致",
            )
        ),
        page_texts={"e1": PAGE_TEXT, "e2": PAGE_TEXT},
    )
    with pytest.raises(CitationValidationError):
        policy.ask("年假有多少天")


def test_conflict_citations_come_from_detector_not_model() -> None:
    """对抗：冲突检测器 evidence_ids 与模型 citation_ids 不一致时，CONFLICT 引用来自检测器。"""
    e1 = _evidence("e1", "d1")
    e2 = _evidence("e2", "d2")
    conflict = ConflictAssessmentDTO(
        is_conflict=True,
        claim_a="年假 15 天",
        claim_b="年假 10 天",
        evidence_ids=("e1", "e2"),
        reason_code=ConflictReasonCode.MUTUALLY_EXCLUSIVE_RULES,
    )
    policy = _make_policy(
        retriever=lambda q: (e1, e2),
        conflict_detector=_FakeConflictDetector(conflict),
        chat_model=_FakeChatModel(
            ModelAnswerDTO(
                status=AnswerStatus.CONFLICT,
                answer="",
                citation_ids=("e1",),  # 模型只返回 e1，与检测器不一致
                conflict_note="两份制度对年假天数规定不一致",
            )
        ),
        page_texts={"e1": PAGE_TEXT, "e2": PAGE_TEXT},
    )
    result = policy.ask("年假有多少天")
    assert result.status is AnswerStatus.CONFLICT
    assert {c.evidence_id for c in result.citations} == {"e1", "e2"}


def test_conflict_detector_forged_quote_rejected_even_if_model_omits() -> None:
    """对抗：冲突检测器证据 quote 伪造（即使模型未引用该 ID）也必须被拒绝。"""
    e1 = _evidence("e1", "d1")
    forged = _evidence("e2", "d2")
    forged.quote = "模型编造的原文"  # e2 的 quote 伪造，与页文本不一致
    conflict = ConflictAssessmentDTO(
        is_conflict=True,
        claim_a="年假 15 天",
        claim_b="年假 10 天",
        evidence_ids=("e1", "e2"),
        reason_code=ConflictReasonCode.MUTUALLY_EXCLUSIVE_RULES,
    )
    policy = _make_policy(
        retriever=lambda q: (e1, forged),
        conflict_detector=_FakeConflictDetector(conflict),
        chat_model=_FakeChatModel(
            ModelAnswerDTO(
                status=AnswerStatus.CONFLICT,
                answer="",
                citation_ids=("e1",),  # 模型只引用 e1，但检测器声称 e2 也冲突
                conflict_note="两份制度对年假天数规定不一致",
            )
        ),
        page_texts={"e1": PAGE_TEXT, "e2": PAGE_TEXT},
    )
    with pytest.raises(CitationValidationError):
        policy.ask("年假有多少天")


def test_rerank_reorders_candidates() -> None:
    """③ 重排结果被消费：rerank 返回反序，冲突判定/生成收到重排后的顺序。"""
    e1 = _evidence("e1", "d1")
    e2 = _evidence("e2", "d2")
    received: list[tuple[Evidence, ...]] = []

    class _RecordingReranker:
        def rerank(self, question, candidates):
            return RerankResultDTO(evidence_ids=("e2", "e1"), degraded=False)

    class _RecordingChat:
        def generate(self, question, evidences):
            received.append(tuple(evidences))
            return ModelAnswerDTO(
                status=AnswerStatus.ANSWERED,
                answer="年假为十五天",
                citation_ids=("e2",),
                conflict_note=None,
            )

    policy = _make_policy(
        retriever=lambda q: (e1, e2),
        conflict_detector=_FakeConflictDetector(_no_conflict()),
        chat_model=_RecordingChat(),
        page_texts={"e2": PAGE_TEXT},
        reranker=_RecordingReranker(),
    )
    policy.ask("年假有多少天")
    assert received[0] == (e2, e1)


def test_rerank_subset_does_not_drop_candidates() -> None:
    """③ 重排返回子集时补全候选，不丢证据；命中项排最前。"""
    e1 = _evidence("e1", "d1")
    e2 = _evidence("e2", "d2")
    received: list[tuple[Evidence, ...]] = []

    class _SubsetReranker:
        def rerank(self, question, candidates):
            return RerankResultDTO(evidence_ids=("e2",), degraded=False)

    class _RecordingChat:
        def generate(self, question, evidences):
            received.append(tuple(evidences))
            return ModelAnswerDTO(
                status=AnswerStatus.ANSWERED,
                answer="年假为十五天",
                citation_ids=("e2",),
                conflict_note=None,
            )

    policy = _make_policy(
        retriever=lambda q: (e1, e2),
        conflict_detector=_FakeConflictDetector(_no_conflict()),
        chat_model=_RecordingChat(),
        page_texts={"e2": PAGE_TEXT},
        reranker=_SubsetReranker(),
    )
    policy.ask("年假有多少天")
    assert {e.evidence_id for e in received[0]} == {"e1", "e2"}
    assert received[0][0].evidence_id == "e2"


def test_evidence_below_threshold_returns_no_evidence() -> None:
    """证据强度不足 → NO_EVIDENCE + warning EVIDENCE_BELOW_THRESHOLD（SPEC §12）。"""
    weak = _evidence("e1", "d1", score=0.001)
    policy = _make_policy(
        retriever=lambda q: (weak,),
        conflict_detector=_FakeConflictDetector(_no_conflict()),
        chat_model=_FakeChatModel(
            ModelAnswerDTO(
                status=AnswerStatus.ANSWERED,
                answer="不应被生成",
                citation_ids=("e1",),
                conflict_note=None,
            )
        ),
        page_texts={"e1": PAGE_TEXT},
        evidence_threshold=0.01,
    )
    result = policy.ask("随便问")
    assert result.status is AnswerStatus.NO_EVIDENCE
    assert result.answer == ""
    assert "EVIDENCE_BELOW_THRESHOLD" in result.warnings
