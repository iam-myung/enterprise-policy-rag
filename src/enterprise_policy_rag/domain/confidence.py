"""回答置信度计算（纯函数，综合可信度 0~1）。

domain 纯净：仅依赖标准库与 domain 内实体/结果类型。
"""

import math

from enterprise_policy_rag.domain.entities import Evidence
from enterprise_policy_rag.domain.result import AnswerStatus


def compute_confidence(
    status: AnswerStatus,
    citations: tuple[Evidence, ...],
    candidates: tuple[Evidence, ...],
    degraded: bool = False,
) -> float:
    """计算综合可信度（0~1），回答「该结果能否直接采信」。

    规则：
    - NO_EVIDENCE → 0.0（无证据，完全不可信）。
    - CONFLICT → 0.35（有信息但制度相互矛盾，不能直接采信）。
    - ANSWERED → 0.6 + 0.4 × 检索强度；degraded 时整体 ×0.8，封顶 1.0。

    检索强度 = 引用证据中最高分在候选集里的 softmax 权重，衡量「被引用证据
    相对其余候选的区分度」——越突出越可信，分数接近时区分度低、可信度回落。
    """
    if status == AnswerStatus.NO_EVIDENCE:
        return 0.0
    if status == AnswerStatus.CONFLICT:
        return 0.35

    if not candidates:
        return 0.0

    scores = [c.score for c in candidates]
    cited_scores = [c.score for c in citations] or scores
    top = max(cited_scores)
    max_score = max(scores)

    denominator = sum(math.exp(s - max_score) for s in scores)
    strength = math.exp(top - max_score) / denominator if denominator > 0 else 0.0

    confidence = 0.6 + 0.4 * strength
    if degraded:
        confidence *= 0.8
    return round(min(1.0, confidence), 4)
