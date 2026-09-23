# 企业内部制度知识库问答系统（enterprise_policy_rag）

面向新员工的企业制度问答系统：从考勤、请假、报销制度 PDF 中检索证据，生成可回看原文、且证据不足时拒答的答案。

> 项目处于 **Phase 1 MVP** 骨架阶段（Step 0）。当前仓库仅包含工程骨架与旧 CASE 只读防线，业务实现将按 `SPEC.md` 的开发顺序 DAG 逐步落地。

## 技术栈

- 单栈 Python：FastAPI + Pydantic + Streamlit + SQLite(SQLAlchemy/Alembic)
- 检索：DashScope Embedding + FAISS + BM25 + RRF + Qwen 重排
- 架构：模块化单体 + Clean Architecture（`domain / application / adapters / interfaces`）
- 部署：Docker Compose 本地演示

## 目录结构

见 `.docs/SPEC.md` §3。核心分层依赖方向：

```
interfaces  → application → domain
adapters    → application → domain
composition → interfaces + application + adapters
domain      → Python 标准库 only
```

## 环境与运行

```powershell
# 安装依赖（uv）
uv sync

# 运行 API（后续 Step 实现后可用）
uv run uvicorn enterprise_policy_rag.interfaces.api.app:app --reload
```

环境变量见 `.env.example`。

## 旧 CASE 只读防线

仓库根目录下 `06_*` ~ `10_*` 为原始学习案例（只读、不跟踪、不修改）。完整性由
`tools/legacy_guard.py` 与 `tools/legacy_manifest.json` 负责：

```powershell
# 基线校验（重新计算 SHA-256，零漂移）
python tools/legacy_guard.py verify

# 新源码运行时引用检查（禁止 sys.path / 相对导入指向旧 CASE）
python tools/legacy_guard.py check-refs

# 重新生成基线 manifest
python tools/legacy_guard.py gen
```

## 文档

- 唯一事实来源：`.docs/SPEC.md`
- 开发契约：`.docs/SPEC.md` §11
