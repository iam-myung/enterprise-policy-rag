"""OpenTelemetry 可观测性适配器（SPEC §10.2）。

TelemetryPort 实现：
- 结构化 JSON 日志（§10.2 字段集）由标准库 logging 输出；
- span 通过 opentelemetry.trace 记录（依赖缺失时退化为纯计时日志）；
- metric 通过 opentelemetry.metrics 记录（依赖缺失时以 DEBUG 日志降级）；
- 所有属性值经 redact_field 脱敏，禁止记录密钥/完整原文/绝对路径/PII；
- 任何 provider 异常均被吞掉，问答链路不受影响。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from types import TracebackType
from typing import Any

from enterprise_policy_rag.application.ports.telemetry import (
    TelemetrySpan,
    redact_field,
)

logger = logging.getLogger("enterprise_policy_rag.telemetry")
_warned: set[str] = set()


def _warn_once(message: str) -> None:
    if message in _warned:
        return
    _warned.add(message)
    logger.warning(message)


def _ensure_handler() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _load_trace_module() -> Any:
    try:
        from opentelemetry import trace

        return trace
    except Exception:  # noqa: BLE001
        return None


def _load_metrics_module() -> Any:
    try:
        from opentelemetry import metrics

        return metrics
    except Exception:  # noqa: BLE001
        return None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _trace_id(trace_module: Any) -> str:
    if trace_module is not None:
        with suppress(Exception):
            context = trace_module.get_current_span().get_span_context()
            if context.is_valid:
                return f"{context.trace_id:032x}"
    return uuid.uuid4().hex


class _OtelSpan:
    """span：计时 + 退出时输出结构化 JSON 日志（可选 OTel span）。"""

    def __init__(self, parent: OtelTelemetry, name: str) -> None:
        self._parent = parent
        self._name = name
        self._start = 0.0
        self._otel_span: Any = None

    def __enter__(self) -> _OtelSpan:
        self._start = time.perf_counter()
        tracer = self._parent._tracer
        if tracer is not None:
            self._otel_span = tracer.start_span(self._name)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        duration_ms = (time.perf_counter() - self._start) * 1000
        status = "error" if exc_type is not None else "ok"
        error_code = ""
        if exc is not None:
            code = getattr(exc, "code", None)
            error_code = getattr(code, "value", "") if code is not None else ""
            if not error_code:
                error_code = type(exc).__name__
        self._parent._emit(
            {
                "level": "INFO",
                "event": "span",
                "operation": self._name,
                "duration_ms": round(duration_ms, 3),
                "status": status,
                "error_code": error_code,
            },
            logging.INFO,
        )
        if self._otel_span is not None:
            with suppress(Exception):
                self._otel_span.end()
        return None


class OtelTelemetry:
    """TelemetryPort 的 OpenTelemetry 实现（可选依赖，安全降级）。"""

    def __init__(self, service_name: str = "enterprise-policy-rag") -> None:
        _ensure_handler()
        self._trace_module = _load_trace_module()
        self._metrics_module = _load_metrics_module()
        self._tracer: Any = None
        self._meter: Any = None
        self._counters: dict[str, Any] = {}
        if self._trace_module is not None:
            self._tracer = self._trace_module.get_tracer(service_name)
        else:
            _warn_once("opentelemetry.trace 不可用，span 退化为纯计时日志")
        if self._metrics_module is not None:
            self._meter = self._metrics_module.get_meter(service_name)
        else:
            _warn_once("opentelemetry.metrics 不可用，指标退化为 DEBUG 日志")

    def record_event(self, name: str, attributes: tuple[tuple[str, str], ...]) -> None:
        sanitized = {key: redact_field(value) for key, value in attributes}
        operation = sanitized.pop("operation", name)
        status = sanitized.pop("status", "ok")
        error_code = sanitized.pop("error_code", "")
        payload: dict[str, object] = {
            "level": "INFO",
            "event": name,
            "trace_id": _trace_id(self._trace_module),
            "operation": operation,
            "status": status,
            "error_code": error_code,
        }
        payload.update(sanitized)
        self._emit(payload, logging.INFO)

    def record_metric(self, name: str, value: float) -> None:
        if self._meter is not None and self._record_metric_otel(name, value):
            return
        self._emit(
            {
                "level": "DEBUG",
                "event": "metric",
                "metric": name,
                "value": value,
                "trace_id": _trace_id(self._trace_module),
            },
            logging.DEBUG,
        )

    def start_span(self, name: str) -> TelemetrySpan:
        return _OtelSpan(self, name)

    def _record_metric_otel(self, name: str, value: float) -> bool:
        try:
            counter = self._counters.get(name)
            if counter is None:
                counter = self._meter.create_counter(name, unit="1", description=name)
                self._counters[name] = counter
            counter.add(value)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _emit(self, payload: dict[str, object], level: int) -> None:
        payload.setdefault("timestamp_utc", _utc_now())
        with suppress(Exception):
            logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))
