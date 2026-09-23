# 项目记忆（当前态）

> 历史见 `DEV_LOG.md`。唯一事实来源：`SPEC.md`。

## Tech Stack & Constraints

- Phase 1 MVP · S 级 · Python（FastAPI + Streamlit + SQLite + FAISS/BM25）
- 解释器：conda `dev_env_311`（3.11.15）
- CI：`pip install -e ".[dev]"`（optional-dependencies.dev 已对齐）

## Current Architecture

- Clean Architecture；三态问答；TelemetryPort；Compose / 本机双进程

## Current Status & Progress

- Prompt-Step **0～18 全闭环**（**18-QA PASS with risks**）
- 门禁（2026-09-24）：ruff 0 / mypy 0 / pytest **225 passed / 1 skipped**
- Git：`main` **0 commits**（F6 仍待用户执行）

## Known Issues & Tech Debt

- 🟡 `migrations/.gitkeep` 仍含过期「占位 / Step 3 在此生成」注释（非 `.py`；迁移已存在）
- 🟡 仓库无 commit，无法用 git diff 证明 18-GREEN「仅改 docstring」；以抽检 + 全绿门禁代替
- 🟡 容器 build/up 原文日志仍缺（Docker engine 不可用）；CI 不含 integration（已登记）

## Pending Tasks & Next Step

- **下一步：用户执行 F6（首次 git commit + 远端 CI）** —— 不在 Prompt-Step HTML 清单内
- Phase 2/3 不在本轮范围
