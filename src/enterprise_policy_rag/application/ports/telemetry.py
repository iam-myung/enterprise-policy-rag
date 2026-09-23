"""可观测性 Port（SPEC §5.320 / §10.2）。

TelemetryPort：结构化事件 / span / metric 三类记录能力；参数脱敏，
不记录完整制度原文 / 密钥 / 绝对路径 / PII。由 adapters.telemetry 实现；
本模块仅依赖标准库与 typing。

脱敏纯函数 redact_field 与 Null Object noop_telemetry 一并在此定义，
作为 Step 14-RED 冻结的合同，Step 14-GREEN 不得修改其断言与语义。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

REDACTED_SECRET = "<redacted:secret>"  # noqa: S105
REDACTED_PATH = "<redacted:path>"
REDACTED_PII = "<redacted:pii>"

_MAX_FIELD_CHARS = 120
_TRUNCATE_SUFFIX = "…"

# 密钥：sk- 前缀 + 20+ 非空白字符（忽略大小写）。
# 真实 DashScope 密钥为 JWT 式（sk- 后含 . / - _ 等非 [A-Za-z0-9] 字符），
# 纯 alnum 或 base64/base64url 字符集均覆盖不全；此处与 domain/result.py
# 的 _SECRET_MARKERS「sk- 前缀」口径对齐，用 20+ 长度阈值避免 risk-/task- 等普通词误判。
_SECRET_RE = re.compile(r"sk-\S{20,}", re.IGNORECASE)
_WIN_PATH_RE = re.compile(r"^[A-Za-z]:[\\/].*")
_POSIX_PATH_RE = re.compile(r"^/.*")
_EMAIL_RE = re.compile(r"^\S+@\S+\.\S+$")
_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")
_ID_CARD_RE = re.compile(r"^\d{18}$")


def redact_field(value: str) -> str:
    r"""脱敏纯函数（Step 14-RED 合同，语义冻结）。

    优先级从上到下：
    1. 空串原样返回。
    2. 含密钥模式 sk- 前缀 + 20+ 非空白字符（忽略大小写，子串匹配）→ REDACTED_SECRET。
    3. 绝对路径（Windows 盘符 或 POSIX 以 / 开头，整体匹配）→ REDACTED_PATH。
    4. PII（邮箱 / 手机号 1[3-9]\d{9} / 18 位身份证，整体匹配）→ REDACTED_PII。
    5. 长度 > 120 的文本（疑似完整制度原文）→ 截断为前 120 字符 + "…"。
    6. 其余原样返回。
    """
    if value == "":
        return value
    if _SECRET_RE.search(value):
        return REDACTED_SECRET
    if _WIN_PATH_RE.match(value) or _POSIX_PATH_RE.match(value):
        return REDACTED_PATH
    if _EMAIL_RE.match(value) or _MOBILE_RE.match(value) or _ID_CARD_RE.match(value):
        return REDACTED_PII
    if len(value) > _MAX_FIELD_CHARS:
        return value[:_MAX_FIELD_CHARS] + _TRUNCATE_SUFFIX
    return value


@dataclass(frozen=True)
class TelemetryEventDTO:
    """结构化事件：name + 键值 attributes（SPEC §10.2 的 event）。"""

    name: str
    attributes: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TelemetryMetricDTO:
    """结构化指标：name + value。"""

    name: str
    value: float


class TelemetrySpan(Protocol):
    """span 记录能力（SPEC §10.2 span 列表）；上下文管理器。"""

    def __enter__(self) -> TelemetrySpan: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class TelemetryPort(Protocol):
    """可观测性 Port（SPEC §5.320）：结构化事件 / span / metric。"""

    def record_event(
        self, name: str, attributes: tuple[tuple[str, str], ...]
    ) -> None: ...

    def record_metric(self, name: str, value: float) -> None: ...

    def start_span(self, name: str) -> TelemetrySpan: ...


class _NoopTelemetry:
    """Null Object：provider 未配置或依赖缺失时的安全默认实现（不抛异常）。"""

    def record_event(
        self, name: str, attributes: tuple[tuple[str, str], ...]
    ) -> None:
        return None

    def record_metric(self, name: str, value: float) -> None:
        return None

    def start_span(self, name: str) -> TelemetrySpan:
        return _NoopSpan()


class _NoopSpan:
    """Null Object span。"""

    def __enter__(self) -> _NoopSpan:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


def noop_telemetry() -> TelemetryPort:
    """返回 Null Object 实现（Step 14-RED 合同）。"""
    return _NoopTelemetry()
