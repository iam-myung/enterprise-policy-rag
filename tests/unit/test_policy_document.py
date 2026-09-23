"""PolicyDocument 不变量测试（SPEC §4.1）。

Step 2-RED：引用尚未实现的 PolicyDocument / DocumentStatus，运行时应以 ImportError 失败。
"""

from datetime import date

import pytest

from enterprise_policy_rag.domain.entities import DocumentStatus, PolicyDocument


def _make_doc(**overrides):
    kwargs = dict(
        id="doc-1",
        title="考勤制度",
        version="v1.0",
        effective_at=date(2024, 1, 1),
        expires_at=date(2024, 12, 31),
        scope="全体员工",
        source_kind="PUBLIC_SAMPLE",
        status=DocumentStatus.ACTIVE,
        sha256="abc",
        page_count=10,
    )
    kwargs.update(overrides)
    return PolicyDocument(**kwargs)


def test_expires_before_effective_rejected():
    with pytest.raises(ValueError):
        _make_doc(effective_at=date(2024, 6, 1), expires_at=date(2024, 1, 1))


def test_expires_equal_effective_allowed():
    doc = _make_doc(effective_at=date(2024, 1, 1), expires_at=date(2024, 1, 1))
    assert doc.expires_at == doc.effective_at


def test_expires_after_effective_allowed():
    doc = _make_doc(effective_at=date(2024, 1, 1), expires_at=date(2024, 12, 31))
    assert doc.expires_at > doc.effective_at


def test_missing_effective_at_is_pending_confirmation():
    doc = _make_doc(effective_at=None, expires_at=None)
    assert doc.effective_at is None
    assert doc.expires_at is None


def test_missing_expires_at_allowed():
    doc = _make_doc(expires_at=None)
    assert doc.expires_at is None
