"""RRF 融合纯函数（SPEC §5.322 / §9.2）。

Reciprocal Rank Fusion：输入两组有序候选 id（按各自分数已排序，rank 1-based），
只使用 rank 计算分数（不混合分值尺度），输出按 rrf_score 降序。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FusionCandidate:
    """融合候选（candidate_id + RRF 分数）。"""

    candidate_id: str
    rrf_score: float


def rrf_fusion(
    dense_ids: tuple[str, ...],
    sparse_ids: tuple[str, ...],
    k: int = 60,
) -> tuple[FusionCandidate, ...]:
    """Reciprocal Rank Fusion（RRF）。

    rrf_score(candidate) = Σ_{r} 1 / (k + rank_r)，其中 rank_r 为候选在每路中
    1-based 的位置；只使用 rank，不混合各路的原始分值尺度。
    """
    scores: dict[str, float] = {}
    for rank, candidate_id in enumerate(dense_ids, start=1):
        scores[candidate_id] = scores.get(candidate_id, 0.0) + 1.0 / (k + rank)
    for rank, candidate_id in enumerate(sparse_ids, start=1):
        scores[candidate_id] = scores.get(candidate_id, 0.0) + 1.0 / (k + rank)

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return tuple(
        FusionCandidate(candidate_id=candidate_id, rrf_score=score)
        for candidate_id, score in ordered
    )
