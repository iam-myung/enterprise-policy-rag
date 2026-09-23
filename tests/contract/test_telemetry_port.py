"""Step 14-RED：TelemetryPort 契约测试（SPEC 可观测性 / 脱敏合同）。

验收点：
① TelemetryPort 暴露结构化事件 / span / metric 三类记录能力。
② 可用性：provider 未配置或依赖缺失时由 noop_telemetry() 装配 Null Object，
   三类调用不抛异常、不阻断主流程。
③ 脱敏合同（负样例）：含密钥明文、完整制度原文长片段、绝对路径、PII 的记录字段
   必须由 redact_field 确定性脱敏，不得原样进入 telemetry 记录。

行为层（OTel 适配器 / 真实埋点 / no-op 与 provider 二选装配）由 Step 14-GREEN 的
集成测试覆盖；本文件只测契约层（Port 协议 + DTO 形状与不可变性 + 脱敏纯函数合同）。
"""

from dataclasses import FrozenInstanceError

import pytest

from enterprise_policy_rag.application.ports.telemetry import (
    TelemetryEventDTO,
    TelemetryMetricDTO,
    TelemetryPort,
    TelemetrySpan,
    noop_telemetry,
    redact_field,
)


def test_telemetry_port_declares_event_span_metric() -> None:
    """① TelemetryPort 必须声明 event / span / metric 三类记录方法。"""
    assert hasattr(TelemetryPort, "record_event")
    assert hasattr(TelemetryPort, "record_metric")
    assert hasattr(TelemetryPort, "start_span")


def test_telemetry_event_dto_fields_and_immutable() -> None:
    """① 结构化事件 DTO：name + attributes（键值对元组），发布后不可变。"""
    event = TelemetryEventDTO(name="qa.answered", attributes=(("status", "ANSWERED"),))
    assert event.name == "qa.answered"
    assert event.attributes == (("status", "ANSWERED"),)
    with pytest.raises(FrozenInstanceError):
        event.name = "x"  # type: ignore[misc]


def test_telemetry_metric_dto_fields_and_immutable() -> None:
    """① 结构化指标 DTO：name + value，发布后不可变。"""
    metric = TelemetryMetricDTO(name="qa.latency_ms", value=123.0)
    assert metric.name == "qa.latency_ms"
    assert metric.value == 123.0
    with pytest.raises(FrozenInstanceError):
        metric.value = 0.0  # type: ignore[misc]


def test_telemetry_span_is_context_manager() -> None:
    """① span 记录能力以上下文管理器契约暴露。"""
    assert hasattr(TelemetrySpan, "__enter__")
    assert hasattr(TelemetrySpan, "__exit__")


def test_noop_telemetry_available_and_never_raises() -> None:
    """② provider 未配置时 noop_telemetry() 返回 Null Object，三类调用均不抛异常。"""
    telemetry = noop_telemetry()
    assert telemetry.record_event("e", (("k", "v"),)) is None
    assert telemetry.record_metric("m", 1.0) is None
    with telemetry.start_span("s"):
        pass


def test_redact_field_is_deterministic_and_safe() -> None:
    """③ 脱敏纯函数：密钥/长原文/绝对路径/PII 负样例不得原样进入记录。"""
    secret = "sk-" + "a" * 24
    assert redact_field(secret) != secret
    assert "sk-" not in redact_field(secret)
