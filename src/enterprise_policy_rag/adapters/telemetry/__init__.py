"""可观测性适配器（SPEC §10.2）。

OpenTelemetry 实现 TelemetryPort；依赖缺失时安全降级为纯计时 JSON 日志。
不记录密钥、完整制度原文、绝对路径或 PII。
"""

from enterprise_policy_rag.adapters.telemetry.otel_telemetry import OtelTelemetry

__all__ = ["OtelTelemetry"]
