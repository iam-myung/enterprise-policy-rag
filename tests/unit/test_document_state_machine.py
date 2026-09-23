"""文档状态机合法/非法迁移测试（SPEC §4.2）。

Step 2-RED：引用尚未实现的 DocumentStatus / can_transition，运行时应以 ImportError 失败。
"""

import pytest

from enterprise_policy_rag.domain.entities import DocumentStatus
from enterprise_policy_rag.domain.policy_rules import can_transition

LEGAL = [
    (DocumentStatus.PENDING, DocumentStatus.PROCESSING),
    (DocumentStatus.PROCESSING, DocumentStatus.ACTIVE),
    (DocumentStatus.PROCESSING, DocumentStatus.FAILED),
    (DocumentStatus.ACTIVE, DocumentStatus.SUPERSEDED),
    (DocumentStatus.ACTIVE, DocumentStatus.EXPIRED),
    (DocumentStatus.FAILED, DocumentStatus.PROCESSING),  # 仅显式重试
]

ILLEGAL = [
    (DocumentStatus.PENDING, DocumentStatus.ACTIVE),
    (DocumentStatus.PENDING, DocumentStatus.FAILED),
    (DocumentStatus.PENDING, DocumentStatus.SUPERSEDED),
    (DocumentStatus.PENDING, DocumentStatus.EXPIRED),
    (DocumentStatus.PROCESSING, DocumentStatus.PENDING),
    (DocumentStatus.PROCESSING, DocumentStatus.SUPERSEDED),
    (DocumentStatus.PROCESSING, DocumentStatus.EXPIRED),
    (DocumentStatus.ACTIVE, DocumentStatus.PENDING),
    (DocumentStatus.ACTIVE, DocumentStatus.PROCESSING),
    (DocumentStatus.ACTIVE, DocumentStatus.FAILED),
    (DocumentStatus.FAILED, DocumentStatus.ACTIVE),
    (DocumentStatus.FAILED, DocumentStatus.SUPERSEDED),
    (DocumentStatus.FAILED, DocumentStatus.EXPIRED),
    (DocumentStatus.FAILED, DocumentStatus.PENDING),
    (DocumentStatus.SUPERSEDED, DocumentStatus.ACTIVE),
    (DocumentStatus.SUPERSEDED, DocumentStatus.PENDING),
    (DocumentStatus.EXPIRED, DocumentStatus.ACTIVE),
    (DocumentStatus.EXPIRED, DocumentStatus.PENDING),
]


@pytest.mark.parametrize("frm,to", LEGAL)
def test_legal_transition(frm, to):
    assert can_transition(frm, to) is True


@pytest.mark.parametrize("frm,to", ILLEGAL)
def test_illegal_transition(frm, to):
    assert can_transition(frm, to) is False
