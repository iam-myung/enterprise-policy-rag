"""enterprise_policy_rag —— 企业内部制度知识库问答系统（Phase 1 MVP）。

模块化单体 + Clean Architecture。依赖方向（SPEC §2.1）：
    interfaces  → application → domain
    adapters    → application → domain
    composition → interfaces + application + adapters
    domain      → Python 标准库 only
"""
