"""DashScopeEmbeddings 分批回归测试。

回归守护：text-embedding 单次批量上限 10，超过须分批再合并（否则报
`batch size is invalid`）；Provider 失败抛 EmbeddingProviderError（映射 502）。
"""

from unittest.mock import patch

import pytest

from enterprise_policy_rag.adapters.llm.dashscope_embeddings import (
    DashScopeEmbeddings,
    EmbeddingProviderError,
)


def _fake_ok_response(input_texts: list[str]) -> object:
    class _Resp:
        status_code = 200
        output = {
            "embeddings": [
                {"embedding": [float(len(input_texts))]} for _ in input_texts
            ]
        }

    return _Resp()


def test_embed_texts_batches_into_groups_of_10() -> None:
    """① 超过 10 条分批调用，每批 ≤10，结果按原顺序合并。"""
    calls: list[list[str]] = []

    def fake_call(model, input, api_key, timeout):
        calls.append(list(input))
        return _fake_ok_response(input)

    with patch(
        "enterprise_policy_rag.adapters.llm.dashscope_embeddings.TextEmbedding.call",
        side_effect=fake_call,
    ):
        emb = DashScopeEmbeddings(api_key="x")
        texts = [f"文本{i}" for i in range(25)]
        vecs = emb.embed_texts(texts)

    assert len(vecs) == 25
    assert [len(c) for c in calls] == [10, 10, 5]
    assert calls[0] == texts[0:10]
    assert calls[1] == texts[10:20]
    assert calls[2] == texts[20:25]


def test_embed_texts_single_batch_no_split() -> None:
    """① 少于等于 10 条只调用一次，不拆分。"""
    calls: list[list[str]] = []

    def fake_call(model, input, api_key, timeout):
        calls.append(list(input))
        return _fake_ok_response(input)

    with patch(
        "enterprise_policy_rag.adapters.llm.dashscope_embeddings.TextEmbedding.call",
        side_effect=fake_call,
    ):
        emb = DashScopeEmbeddings(api_key="x")
        vecs = emb.embed_texts([f"t{i}" for i in range(10)])

    assert len(vecs) == 10
    assert len(calls) == 1


def test_embed_texts_propagates_provider_error() -> None:
    """① 某批 Provider 失败抛 EmbeddingProviderError（上层映射 502）。"""

    class _Err:
        status_code = 400
        code = "InvalidParameter"
        message = "batch size invalid"

    def fake_call(model, input, api_key, timeout):
        return _Err()

    with patch(
        "enterprise_policy_rag.adapters.llm.dashscope_embeddings.TextEmbedding.call",
        side_effect=fake_call,
    ):
        emb = DashScopeEmbeddings(api_key="x")
        with pytest.raises(EmbeddingProviderError):
            emb.embed_texts([f"t{i}" for i in range(25)])
