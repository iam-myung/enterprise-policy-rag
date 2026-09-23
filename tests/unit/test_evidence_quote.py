"""Evidence.quote 截取不变量测试（SPEC §4.1）。

Step 2-RED：引用尚未实现的 Evidence / validate_evidence_quote，运行时应以 ImportError 失败。
"""

import pytest

from enterprise_policy_rag.domain.citation_rules import validate_evidence_quote
from enterprise_policy_rag.domain.entities import Evidence

PAGE_TEXT = "员工请假须提前一天申请，经部门负责人批准。"


def _evidence(**overrides):
    kwargs = dict(
        evidence_id="e1",
        chunk_id="c1",
        document_id="doc-1",
        title="请假制度",
        version="v1.0",
        page=1,
        char_start=0,
        char_end=10,
        quote=PAGE_TEXT[0:10],
        page_text_sha256="x",
        score=0.9,
    )
    kwargs.update(overrides)
    return Evidence(**kwargs)


def test_quote_matches_page_slice():
    ev = _evidence()
    validate_evidence_quote(ev, PAGE_TEXT)  # 不抛异常


def test_quote_mismatch_rejected():
    ev = _evidence(quote="模型编造的文本")
    with pytest.raises(ValueError):
        validate_evidence_quote(ev, PAGE_TEXT)
