r"""Step 14-RED：telemetry 脱敏纯函数确定性回归测试。

redact_field(value: str) -> str 脱敏合同（优先级从上到下）：
1. 空串原样返回。
2. 密钥模式 sk-[A-Za-z0-9]{20,}（子串匹配）→ REDACTED_SECRET。
3. 绝对路径（Windows 盘符 或 POSIX 以 / 开头，整体匹配）→ REDACTED_PATH。
4. PII（邮箱 / 手机号 1[3-9]\d{9} / 18 位身份证，整体匹配）→ REDACTED_PII。
5. 长度 > 120 的文本（疑似完整制度原文）→ 截断为前 120 字符 + "…"。
6. 其余原样返回。

本文件是对脱敏合同的确定性断言，Step 14-GREEN 必须实现到完全一致，不得修改这些断言。
"""

from enterprise_policy_rag.application.ports.telemetry import (
    REDACTED_PATH,
    REDACTED_PII,
    REDACTED_SECRET,
    redact_field,
)


def test_redact_field_keeps_empty() -> None:
    assert redact_field("") == ""


def test_redact_field_dashscope_api_key() -> None:
    key = "sk-" + "a" * 24
    assert redact_field(key) == REDACTED_SECRET
    assert redact_field(f"Bearer {key}") == REDACTED_SECRET


def test_redact_field_real_key_charsets() -> None:
    """真实密钥格式（14-FIX）：sk- 后含 base64url(-_)/base64(+/=)/JWT(.) 特殊字符也须脱敏。"""
    base64url = "sk-a1B2c3D4" + "-_a1B2c3D4e5F6g7H8"
    base64 = "sk-a1B2c3D4e5F6g7H8" + "+/a1B2c3D4e5F6g7H8=="
    jwt_like = "sk-eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature"
    assert redact_field(base64url) == REDACTED_SECRET
    assert redact_field(base64) == REDACTED_SECRET
    assert redact_field(jwt_like) == REDACTED_SECRET


def test_redact_field_windows_absolute_path() -> None:
    assert redact_field(r"D:\MiniConda\envs\dev_env_311\python.exe") == REDACTED_PATH


def test_redact_field_posix_absolute_path() -> None:
    assert redact_field("/etc/passwd") == REDACTED_PATH


def test_redact_field_email_pii() -> None:
    assert redact_field("alice@example.com") == REDACTED_PII


def test_redact_field_mobile_pii() -> None:
    assert redact_field("13812345678") == REDACTED_PII


def test_redact_field_id_card_pii() -> None:
    assert redact_field("110101199003077777") == REDACTED_PII


def test_redact_field_long_policy_text_truncated() -> None:
    text = "制度条文" * 100  # 400 字符，> 120 阈值
    result = redact_field(text)
    assert len(result) == 121
    assert result.endswith("…")
    assert result.startswith(text[:120])


def test_redact_field_ordinary_text_unchanged() -> None:
    assert redact_field("qa.latency_ms") == "qa.latency_ms"
    assert redact_field("ANSWERED") == "ANSWERED"
