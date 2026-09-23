"""Step 8-RED：RerankerPort 契约测试（SPEC §5.316 / §6.2）。

验收点：
① RerankerPort 只能返回已给定 evidence ID；失败按配置退化为 RRF 并标记 RERANKER_DEGRADED。
"""

from dataclasses import FrozenInstanceError

import pytest

from enterprise_policy_rag.application.ports.models import (
    RerankerPort,
    RerankResultDTO,
)


def test_rerank_result_fields() -> None:
    """RerankResultDTO 字段：evidence_ids（排序后）+ degraded（是否退化为 RRF）。"""
    result = RerankResultDTO(evidence_ids=("e2", "e1"), degraded=False)
    assert result.evidence_ids == ("e2", "e1")
    assert result.degraded is False


def test_rerank_result_is_immutable() -> None:
    """重排结果不可变。"""
    result = RerankResultDTO(evidence_ids=("e1",), degraded=True)
    with pytest.raises(FrozenInstanceError):
        result.degraded = False  # type: ignore[misc]


def test_reranker_port_declares_rerank() -> None:
    """RerankerPort 协议必须声明 rerank 方法（SPEC §5.316）。"""
    assert hasattr(RerankerPort, "rerank")
