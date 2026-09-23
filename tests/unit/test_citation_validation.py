"""Step 9-RED：引用 ID 校验纯函数测试（SPEC §6.2 / §9.2）。

验收点②：引用校验——模型返回未知 ID → 上层映射 CITATION_VALIDATION_FAILED。
本文件聚焦 domain 层 validate_citation_ids 纯函数（标准库，无框架依赖）。
"""

import pytest

from enterprise_policy_rag.domain.citation_rules import validate_citation_ids


def test_citation_ids_subset_is_valid() -> None:
    """citation_ids 是给定 evidence ids 子集 → 不抛异常。"""
    validate_citation_ids(("e1", "e2"), {"e1", "e2", "e3"})


def test_citation_ids_unknown_id_rejected() -> None:
    """citation_ids 含未知 ID → 抛 ValueError（上层映射 CITATION_VALIDATION_FAILED）。"""
    with pytest.raises(ValueError):
        validate_citation_ids(("e1", "e99"), {"e1", "e2"})


def test_citation_ids_empty_is_valid() -> None:
    """空 citation_ids（NO_EVIDENCE 场景）→ 不抛异常。"""
    validate_citation_ids((), {"e1", "e2"})


def test_citation_ids_all_unknown_rejected() -> None:
    """全部为未知 ID → 抛 ValueError。"""
    with pytest.raises(ValueError):
        validate_citation_ids(("e9", "e10"), {"e1", "e2"})
