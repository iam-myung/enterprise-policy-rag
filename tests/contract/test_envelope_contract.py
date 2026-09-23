"""Envelope 互斥与 error.context 白名单脱敏契约测试（SPEC §6.1）。

Step 1-RED：引用尚未实现的 OperationEnvelope / ErrorDetail / validate_error_context，
运行时应以 ImportError 失败。
"""

import pytest

from enterprise_policy_rag.domain.errors import ErrorCode
from enterprise_policy_rag.domain.result import (
    CONTEXT_ALLOWED_KEYS,
    ErrorDetail,
    OperationEnvelope,
    validate_error_context,
)


def _success_envelope(**overrides):
    kwargs = dict(
        success=True,
        data={"answer": "dummy"},
        error=None,
        message="ok",
        trace_id="trace-1",
    )
    kwargs.update(overrides)
    return OperationEnvelope(**kwargs)


def _failure_envelope(**overrides):
    kwargs = dict(
        success=False,
        data=None,
        error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message="boom"),
        message="request failed",
        trace_id="trace-1",
    )
    kwargs.update(overrides)
    return OperationEnvelope(**kwargs)


# ---- ① Envelope 互斥（SPEC §6.1）----

def test_success_requires_data_and_no_error():
    env = _success_envelope()
    assert env.success is True
    assert env.data is not None
    assert env.error is None


def test_failure_requires_error_and_no_data():
    env = _failure_envelope()
    assert env.success is False
    assert env.data is None
    assert env.error is not None


def test_success_with_none_data_rejected():
    with pytest.raises(ValueError):
        _success_envelope(data=None)


def test_success_with_error_rejected():
    with pytest.raises(ValueError):
        _success_envelope(error=ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message="x"))


def test_failure_with_data_rejected():
    with pytest.raises(ValueError):
        _failure_envelope(data={"unexpected": True})


def test_failure_with_none_error_rejected():
    with pytest.raises(ValueError):
        _failure_envelope(error=None)


# ---- ③ error.context 白名单脱敏（SPEC §6.1）----

def test_context_whitelist_defined():
    assert "field_name" in CONTEXT_ALLOWED_KEYS


def test_whitelisted_context_accepted():
    validate_error_context({"field_name": "question"})


def test_non_whitelisted_key_rejected():
    with pytest.raises(ValueError):
        validate_error_context({"api_key": "sk-1234"})


def test_secret_value_rejected():
    with pytest.raises(ValueError):
        validate_error_context({"field_name": "sk-9f8e7d6c5b4a3f2e1d0c"})


def test_absolute_path_rejected():
    with pytest.raises(ValueError):
        validate_error_context({"field_name": "C:\\Users\\admin\\secret.txt"})


def test_full_source_text_rejected():
    with pytest.raises(ValueError):
        validate_error_context({"field_name": "完整制度原文" * 200})


def test_stack_trace_rejected():
    with pytest.raises(ValueError):
        validate_error_context({"field_name": "Traceback (most recent call last): ..."})


def test_error_detail_rejects_sensitive_context():
    with pytest.raises(ValueError):
        ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message="boom",
            context={"field_name": "C:\\absolute\\path"},
        )
