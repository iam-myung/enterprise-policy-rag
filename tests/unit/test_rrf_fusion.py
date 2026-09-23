"""Step 7-RED：RRF 融合纯函数测试（SPEC §5.322 / §9.2）。

验收点：
② rrf_fusion 纯函数：输入两组候选 → 融合结果只来自两路输入；排序确定；RRF 参数化。
"""

import pytest

from enterprise_policy_rag.application.qa.rrf_fusion import (
    FusionCandidate,
    rrf_fusion,
)


def test_fusion_candidates_only_from_inputs() -> None:
    """融合结果只来自两路输入，无外来候选。"""
    dense = ("a", "b", "c")
    sparse = ("b", "d")
    result = rrf_fusion(dense, sparse, k=60)
    ids = {c.candidate_id for c in result}
    assert ids == {"a", "b", "c", "d"}


def test_fusion_ordering_deterministic() -> None:
    """融合结果按 rrf_score 降序，排序确定。"""
    dense = ("a", "b")
    sparse = ("b", "a")
    result = rrf_fusion(dense, sparse, k=60)
    scores = [c.rrf_score for c in result]
    assert scores == sorted(scores, reverse=True)


def test_fusion_multi_hit_scores_higher() -> None:
    """两路都命中的候选 rrf_score 高于单路命中的候选。"""
    dense = ("a", "b")
    sparse = ("a",)  # a 两路命中，b 仅 dense 命中
    result = rrf_fusion(dense, sparse, k=60)
    by_id = {c.candidate_id: c.rrf_score for c in result}
    assert by_id["a"] > by_id["b"]


def test_rrf_is_parameterized() -> None:
    """RRF 参数化：k 不同 → 分数不同，且符合 1/(k+rank) 公式。"""
    dense = ("a", "b")
    sparse = ("a", "c")
    r60 = {c.candidate_id: c.rrf_score for c in rrf_fusion(dense, sparse, k=60)}
    r10 = {c.candidate_id: c.rrf_score for c in rrf_fusion(dense, sparse, k=10)}

    # a 在 dense rank1 + sparse rank1 → 2/(k+1)
    assert r60["a"] == pytest.approx(2 / (60 + 1))
    assert r10["a"] == pytest.approx(2 / (10 + 1))
    # b 仅在 dense rank2 → 1/(k+2)
    assert r60["b"] == pytest.approx(1 / (60 + 2))
    # k 不同 → 分数不同
    assert r60["a"] != r10["a"]


def test_fusion_handles_empty_input() -> None:
    """某一路为空仍能融合另一路。"""
    result = rrf_fusion((), ("a", "b"), k=60)
    assert {c.candidate_id for c in result} == {"a", "b"}
    assert result[0].candidate_id == "a"  # sparse rank1


def test_fusion_candidate_type() -> None:
    """FusionCandidate 为不可变类型，字段 candidate_id / rrf_score。"""
    cand = FusionCandidate(candidate_id="a", rrf_score=0.5)
    assert cand.candidate_id == "a"
    assert cand.rrf_score == 0.5
