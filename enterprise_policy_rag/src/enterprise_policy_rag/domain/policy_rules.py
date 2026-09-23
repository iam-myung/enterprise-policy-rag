"""制度状态机与版本规则（占位）。

Step 2-GREEN 实现 SPEC §4.2 文档状态机：
    PENDING → PROCESSING → ACTIVE → SUPERSEDED / EXPIRED；FAILED → PROCESSING（仅显式重试）。

Step 0 禁止写入任何业务实现。
"""
