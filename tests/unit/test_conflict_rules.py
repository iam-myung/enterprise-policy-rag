"""Step 8-RED：冲突判定合同确定性规则测试（SPEC §4.4）。

验收点：
③ 冲突判定合同 SPEC §4.4 四条条件；版本取代关系不判冲突。
"""

from enterprise_policy_rag.domain.conflict_rules import (
    conflict_eligible,
    has_multiple_documents,
    is_version_superseded,
)
from enterprise_policy_rag.domain.entities import Evidence


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


def test_has_multiple_documents() -> None:
    """§4.4 条件 1：候选证据至少来自两份不同制度。"""
    assert has_multiple_documents((_evidence("e1", "d1"), _evidence("e2", "d2")))
    assert not has_multiple_documents((_evidence("e1", "d1"), _evidence("e2", "d1")))


def test_is_version_superseded() -> None:
    """§4.4 条件 4：存在版本取代关系。"""
    superseded_pairs = frozenset({("d2", "d1")})  # d2 取代 d1
    assert is_version_superseded("d2", "d1", superseded_pairs)
    assert not is_version_superseded("d1", "d2", superseded_pairs)
    assert not is_version_superseded("d3", "d1", superseded_pairs)


def test_conflict_eligible_multiple_documents() -> None:
    """两份不同制度、无取代关系 → 满足冲突前置条件。"""
    candidates = (_evidence("e1", "d1"), _evidence("e2", "d2"))
    assert conflict_eligible(candidates, superseded_pairs=frozenset())


def test_conflict_eligible_single_document() -> None:
    """仅一份制度 → 不满足（§4.4 条件 1）。"""
    candidates = (_evidence("e1", "d1"), _evidence("e2", "d1"))
    assert not conflict_eligible(candidates, superseded_pairs=frozenset())


def test_conflict_eligible_version_superseded() -> None:
    """存在版本取代关系 → 不判冲突（§4.4 条件 4）。"""
    candidates = (_evidence("e1", "d1"), _evidence("e2", "d2"))
    superseded_pairs = frozenset({("d2", "d1")})  # d2 取代 d1
    assert not conflict_eligible(candidates, superseded_pairs)


def test_conflict_eligible_rejects_invalid_quote_interval() -> None:
    """§4.4 条件 3：quote 长度与字符区间不一致 → 不判冲突。"""
    bad = _evidence("e2", "d2")
    bad.quote = "xx"  # 长度 2，但 char_end - char_start = 1
    candidates = (_evidence("e1", "d1"), bad)
    assert not conflict_eligible(candidates, superseded_pairs=frozenset())


def test_conflict_eligible_rejects_empty_version() -> None:
    """§4.4 条件 3：version 缺失 → 不判冲突。"""
    bad = _evidence("e2", "d2")
    bad.version = ""
    candidates = (_evidence("e1", "d1"), bad)
    assert not conflict_eligible(candidates, superseded_pairs=frozenset())


def test_conflict_eligible_rejects_bad_page_hash() -> None:
    """§4.4 条件 3：page_text_sha256 非 64 位 → 不判冲突。"""
    bad = _evidence("e2", "d2")
    bad.page_text_sha256 = "deadbeef"  # 非 64 位 hex
    candidates = (_evidence("e1", "d1"), bad)
    assert not conflict_eligible(candidates, superseded_pairs=frozenset())
