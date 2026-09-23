"""ErrorCode 全集与 HTTP 映射契约测试（SPEC §6.2）。

Step 1-RED：引用尚未实现的 ErrorCode，运行时应以 ImportError 失败。
"""

import pytest

from enterprise_policy_rag.domain.errors import ErrorCode

# SPEC §6.2 表：ErrorCode -> HTTP 状态码
EXPECTED_HTTP_STATUS = {
    "VALIDATION_ERROR": 422,
    "UNSUPPORTED_FILE_TYPE": 415,
    "FILE_TOO_LARGE": 413,
    "DOCUMENT_METADATA_REQUIRED": 422,
    "DUPLICATE_DOCUMENT": 409,
    "DOCUMENT_NOT_FOUND": 404,
    "DOCUMENT_NOT_READY": 409,
    "DOCUMENT_PARSE_FAILED": 422,
    "INDEX_BUILD_FAILED": 500,
    "EMBEDDING_PROVIDER_ERROR": 502,
    "RERANKER_PROVIDER_ERROR": 502,
    "LLM_PROVIDER_ERROR": 502,
    "CITATION_VALIDATION_FAILED": 502,
    "INTERNAL_ERROR": 500,
}


def test_error_code_full_set():
    """ErrorCode 必须包含 SPEC §6.2 的全部 14 个错误码，不多不少。"""
    assert len(ErrorCode) == 14
    assert {member.name for member in ErrorCode} == set(EXPECTED_HTTP_STATUS)


@pytest.mark.parametrize("name", sorted(EXPECTED_HTTP_STATUS))
def test_error_code_http_mapping(name):
    """每个 ErrorCode 的 http_status 必须与 SPEC §6.2 表一致。"""
    code = ErrorCode[name]
    assert code.http_status == EXPECTED_HTTP_STATUS[name]
