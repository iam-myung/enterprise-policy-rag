"""DashScope Embedding 适配器（SPEC §9.4：30s 超时）。

Provider 失败抛 EmbeddingProviderError；上层映射为 EMBEDDING_PROVIDER_ERROR（502）。
"""

import os

from dashscope import TextEmbedding


class EmbeddingProviderError(Exception):
    """Embedding 供应商失败（超时 / 限流 / 服务错误）。"""


class DashScopeEmbeddings:
    """DashScope TextEmbedding 供应商。

    model 默认取环境变量 EMBEDDING_MODEL；超时默认 30s（SPEC §9.4）。
    实现 __call__ 以便作为 callable 注入 FaissIndex。
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 30,
    ) -> None:
        self._api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        self._model = model or os.environ.get(
            "EMBEDDING_MODEL", "text-embedding-v3"
        )
        self._timeout = timeout

    # DashScope text-embedding 单次批量上限 10；超过需分批再合并。
    _BATCH_SIZE = 10

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for start in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[start : start + self._BATCH_SIZE]
            resp = TextEmbedding.call(
                model=self._model,
                input=batch,
                api_key=self._api_key,
                timeout=self._timeout,
            )
            if resp.status_code != 200:
                raise EmbeddingProviderError(
                    f"embedding failed: status={resp.status_code} "
                    f"code={getattr(resp, 'code', None)} "
                    f"message={getattr(resp, 'message', '')}"
                )
            results.extend(item["embedding"] for item in resp.output["embeddings"])
        return results

    def __call__(self, texts: list[str]) -> list[list[float]]:
        return self.embed_texts(texts)
