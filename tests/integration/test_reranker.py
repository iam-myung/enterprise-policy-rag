"""Step 8-RED：QwenReranker 集成测试（SPEC §5.316 / §6.2）。

验收点：
① RerankerPort 只能返回已给定 evidence ID；失败按配置退化为 RRF 并标记 RERANKER_DEGRADED。

使用 fake provider（不调用真实重排模型）。
"""

import pytest

from enterprise_policy_rag.adapters.retrieval.qwen_reranker import (
    QwenReranker,
    RerankerProviderError,
)
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.errors import AppError, ErrorCode


def _evidence(evidence_id: str, doc_id: str, score: float = 1.0) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        chunk_id=f"{evidence_id}-chunk",
        document_id=doc_id,
        title="制度",
        version="v1",
        page=1,
        char_start=0,
        char_end=1,
        quote="x",
        page_text_sha256="0" * 64,
        score=score,
    )


def test_reranker_only_returns_given_ids() -> None:
    """正常路径：返回排序后的已给定 evidence ID，degraded=False。"""
    candidates = (
        _evidence("e1", "d1", score=1.0),
        _evidence("e2", "d2", score=2.0),
        _evidence("e3", "d3", score=3.0),
    )
    provider = lambda question, cands: ["e2", "e1", "e3"]  # noqa: E731
    reranker = QwenReranker(provider)
    result = reranker.rerank("年假有多少天", candidates)
    assert result.evidence_ids == ("e2", "e1", "e3")
    assert result.degraded is False


def test_reranker_rejects_unknown_ids() -> None:
    """Provider 返回未给定 ID → 退化为 RRF（degraded=True），且只含给定 ID。"""
    candidates = (
        _evidence("e1", "d1", score=1.0),
        _evidence("e2", "d2", score=2.0),
    )
    provider = lambda question, cands: ["e9"]  # noqa: E731  # 未知 ID
    reranker = QwenReranker(provider)
    result = reranker.rerank("年假有多少天", candidates)
    assert result.degraded is True
    assert set(result.evidence_ids).issubset({"e1", "e2"})


def test_reranker_degradation_on_provider_failure() -> None:
    """Provider 抛异常 → 退化为 RRF（degraded=True），不向上抛异常。"""
    candidates = (
        _evidence("e1", "d1", score=1.0),
        _evidence("e2", "d2", score=2.0),
    )

    def provider(question, cands):
        raise RuntimeError("provider down")

    reranker = QwenReranker(provider)
    result = reranker.rerank("年假有多少天", candidates)
    assert result.degraded is True
    assert set(result.evidence_ids).issubset({"e1", "e2"})


def test_reranker_no_degrade_raises_on_provider_failure() -> None:
    """allow_degrade=False 且 Provider 抛异常 → 抛 RerankerProviderError，不退化。"""
    candidates = (
        _evidence("e1", "d1", score=1.0),
        _evidence("e2", "d2", score=2.0),
    )

    def provider(question, cands):
        raise RuntimeError("provider down")

    reranker = QwenReranker(provider, allow_degrade=False)
    with pytest.raises(RerankerProviderError):
        reranker.rerank("年假有多少天", candidates)


def test_reranker_no_degrade_raises_on_unknown_ids() -> None:
    """allow_degrade=False 且 Provider 返回未知 ID → 抛 RerankerProviderError。"""
    candidates = (
        _evidence("e1", "d1", score=1.0),
        _evidence("e2", "d2", score=2.0),
    )
    provider = lambda question, cands: ["e9"]  # noqa: E731
    reranker = QwenReranker(provider, allow_degrade=False)
    with pytest.raises(RerankerProviderError):
        reranker.rerank("年假有多少天", candidates)


def test_reranker_provider_error_is_app_error() -> None:
    """RerankerProviderError 继承 AppError → 502 RERANKER_PROVIDER_ERROR（QA 回归）。"""
    err = RerankerProviderError("重排失败")
    assert isinstance(err, AppError)
    assert err.code is ErrorCode.RERANKER_PROVIDER_ERROR
    assert err.code.http_status == 502
