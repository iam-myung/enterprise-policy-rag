"""UI 侧 API 客户端（SPEC §2.2 interfaces.ui）。

UI 只依赖本客户端，不直连数据库/索引/模型。
统一解析 Envelope：成功返回 data，失败抛 ApiError（code + 可读 message）。
"""

import os
from typing import Any, cast

import httpx


class ApiError(Exception):
    """API 失败（携带 ErrorCode + 可读消息，SPEC §6.2）。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _read_request_timeout() -> float:
    """从环境变量读取 UI 请求超时秒数（默认 45s）。"""
    raw = os.environ.get("REQUEST_TIMEOUT_SECONDS", "45").strip()
    try:
        return float(raw)
    except ValueError:
        return 45.0


class ApiClient:
    """封装对 FastAPI 的调用（SPEC §8 内嵌 API 合约）。"""

    def __init__(
        self, base_url: str | None = None, timeout: float | None = None
    ) -> None:
        self._base_url = (
            base_url or os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
        ).rstrip("/")
        self._timeout = timeout if timeout is not None else _read_request_timeout()

    @property
    def base_url(self) -> str:
        return self._base_url

    def health(self) -> dict[str, Any]:
        """GET /health（SPEC §8.2）。"""
        return self._unwrap(self._get("/health"))

    def list_documents(self, status: str | None = None) -> dict[str, Any]:
        """GET /api/v1/documents（SPEC §8.4）→ {items, corpus_revision}。"""
        params = {"status": status} if status else None
        return self._unwrap(self._get("/api/v1/documents", params=params))

    def ask(self, question: str, top_k: int = 5) -> dict[str, Any]:
        """POST /api/v1/questions（SPEC §8.5）→ QuestionAnswerDTO。"""
        return self._unwrap(
            self._post("/api/v1/questions", {"question": question, "top_k": top_k})
        )

    def absolute_url(self, path: str) -> str:
        """把站内相对 source_url 转为完整 URL（供原文回看）。"""
        return f"{self._base_url}{path}"

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            resp = httpx.get(f"{self._base_url}{path}", params=params, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise ApiError("INTERNAL_ERROR", f"API 不可达：{exc}") from exc
        return cast(dict[str, Any], resp.json())

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = httpx.post(f"{self._base_url}{path}", json=payload, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise ApiError("INTERNAL_ERROR", f"API 不可达：{exc}") from exc
        return cast(dict[str, Any], resp.json())

    @staticmethod
    def _unwrap(envelope: dict[str, Any]) -> dict[str, Any]:
        """解析统一 Envelope（SPEC §6.1）：成功返回 data，失败抛 ApiError。"""
        if envelope.get("success"):
            return cast(dict[str, Any], envelope.get("data"))
        error = envelope.get("error") or {}
        raise ApiError(
            cast(str, error.get("code", "INTERNAL_ERROR")),
            cast(str, error.get("message", "请求失败")),
        )
