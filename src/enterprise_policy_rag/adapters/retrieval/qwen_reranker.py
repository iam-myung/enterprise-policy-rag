"""Qwen 重排适配器（SPEC §5.316 / §6.2）。

实现 RerankerPort：只能返回已给定 evidence ID；Provider 失败或返回未知 ID 时，
按配置退化为 RRF 并标记 degraded（上层映射 warnings 中的 RERANKER_DEGRADED）。
"""

from collections.abc import Callable

from enterprise_policy_rag.application.ports.models import RerankResultDTO
from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.errors import AppError, ErrorCode


class RerankerProviderError(AppError):
    """重排 Provider 失败且不允许退化 → 502 RERANKER_PROVIDER_ERROR（SPEC §6.2）。"""

    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.RERANKER_PROVIDER_ERROR, message)


class QwenReranker:
    """Qwen 重排适配器。

    provider：可调用，输入 (question, candidates) 返回排序后的 evidence_id 列表；
    allow_degrade：失败时是否退化为 RRF（按原 score 降序），默认 True。
    """

    def __init__(
        self,
        provider: Callable[[str, tuple[Evidence, ...]], list[str]],
        allow_degrade: bool = True,
    ) -> None:
        self._provider = provider
        self._allow_degrade = allow_degrade

    def rerank(
        self, question: str, candidates: tuple[Evidence, ...]
    ) -> RerankResultDTO:
        given_ids = {c.evidence_id for c in candidates}
        try:
            ordered = tuple(self._provider(question, candidates))
        except Exception as exc:
            if not self._allow_degrade:
                raise RerankerProviderError("重排 Provider 失败且不允许退化") from exc
            return self._degrade(candidates)

        if not set(ordered).issubset(given_ids):
            if not self._allow_degrade:
                raise RerankerProviderError("重排 Provider 返回未知 evidence ID")
            return self._degrade(candidates)
        return RerankResultDTO(evidence_ids=ordered, degraded=False)

    def _degrade(self, candidates: tuple[Evidence, ...]) -> RerankResultDTO:
        ordered = sorted(candidates, key=lambda c: c.score, reverse=True)
        return RerankResultDTO(
            evidence_ids=tuple(c.evidence_id for c in ordered),
            degraded=True,
        )
