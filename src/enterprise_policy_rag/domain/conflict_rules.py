"""冲突判定确定性规则（SPEC §4.4）。

条件 1（至少两份不同制度）、条件 3（evidence 完整性校验）与条件 4（版本取代
不判冲突）为确定性前置条件，语义互斥判断（条件 2）由 ConflictDetectorPort 完成。
"""

from itertools import combinations

from enterprise_policy_rag.domain.entities import Evidence


def has_multiple_documents(candidates: tuple[Evidence, ...]) -> bool:
    """§4.4 条件 1：候选证据至少来自两份不同制度。"""
    return len({c.document_id for c in candidates}) >= 2


def evidence_integrity_valid(evidence: Evidence) -> bool:
    """§4.4 条件 3：evidence 确定性完整性校验。

    校验版本非空、字符区间合法、quote 长度与字符区间一致、页文本 hash 为 64 位。
    「原文子串精确校验」（quote == page_text[char_start:char_end]）依赖 page_text，
    由上游 Evidence 构造 / 引用校验（citation_rules.validate_evidence_quote）保证。
    """
    if not evidence.version:
        return False
    if evidence.char_start < 0 or evidence.char_end <= evidence.char_start:
        return False
    if len(evidence.quote) != evidence.char_end - evidence.char_start:
        return False
    return len(evidence.page_text_sha256) == 64


def is_version_superseded(
    superseding_doc_id: str,
    superseded_doc_id: str,
    superseded_pairs: frozenset[tuple[str, str]],
) -> bool:
    """§4.4 条件 4：判断是否存在「新版本取代旧版本」关系。"""
    return (superseding_doc_id, superseded_doc_id) in superseded_pairs


def conflict_eligible(
    candidates: tuple[Evidence, ...],
    superseded_pairs: frozenset[tuple[str, str]],
) -> bool:
    """§4.4 确定性前置条件（条件 1 + 条件 3 + 条件 4）。

    至少两份不同制度、所有 evidence 通过完整性校验，
    且任意两份制度之间不存在版本取代关系。
    """
    if not candidates:
        return False
    # 条件 3：所有候选 evidence 通过完整性校验。
    if not all(evidence_integrity_valid(c) for c in candidates):
        return False
    # 条件 1：至少两份不同制度。
    if not has_multiple_documents(candidates):
        return False
    # 条件 4：无版本取代关系。
    for a, b in combinations(candidates, 2):
        if a.document_id == b.document_id:
            continue
        if is_version_superseded(a.document_id, b.document_id, superseded_pairs):
            return False
        if is_version_superseded(b.document_id, a.document_id, superseded_pairs):
            return False
    return True
