# 企业内部制度知识库问答系统（enterprise_policy_rag）

面向新员工的企业制度问答系统：从考勤、请假、报销制度 PDF 中检索证据，生成可回看原文、且证据不足时拒答的答案。

## 核心能力

- **混合检索**：DashScope Embedding + FAISS（稠密）+ BM25（稀疏）+ RRF 融合 + Qwen 重排
- **稳定引用**：答案引用由系统从 chunk 按字符区间截取，模型只选 evidence ID，无法伪造原文
- **三态回答**：`ANSWERED`（有证据）/ `NO_EVIDENCE`（拒答，不编造）/ `CONFLICT`（多份制度冲突并列）
- **原文回看**：每条引用带站内 `source_url`，可回看对应 PDF 页
- **基线与目标方案评测**：Recall@K、引用正确率、拒答率、延迟、退化标记等确定性指标

## 技术栈

- 单栈 Python：FastAPI + Pydantic + Streamlit + SQLite（SQLAlchemy/Alembic）
- 检索：DashScope Embedding + FAISS + BM25 + RRF + Qwen 重排
- 架构：模块化单体 + Clean Architecture（`domain / application / adapters / interfaces`）
- 部署：Docker Compose 本地演示

## 目录结构

应用与配置在**仓库根**；Python 包为 `src/enterprise_policy_rag/`。详见 `.docs/SPEC.md` §3。分层依赖方向（import-linter 强制）：

```
interfaces  → application → domain
adapters    → application → domain
composition → interfaces + application + adapters
domain      → Python 标准库 only
```

## 环境与运行

```powershell
# 推荐：Conda 环境 dev_env_311（与仓库工程规则一致）
# 首次：pip install -e .
$py = "D:\MiniConda\envs\dev_env_311\python.exe"   # 按本机 conda 路径调整

# 1. 启动 API（默认 http://127.0.0.1:8001，见 .env APP_PORT）
$env:PYTHONPATH = "src"
& $py -m uvicorn enterprise_policy_rag.composition:create_app --factory --host 127.0.0.1 --port 8001

# 2. 启动 UI（http://127.0.0.1:8501；API_BASE_URL 指向同一端口）
& $py -m streamlit run src/enterprise_policy_rag/interfaces/ui/app.py

# 3. 导入制度 PDF（CLI）
& $py -m enterprise_policy_rag.composition ingest --file <pdf> --title ... --version ...

# 4. 评测（基线 vs 目标，读 active corpus revision）
& $py -m enterprise_policy_rag.composition evaluate --cases evaluation/cases/phase1.jsonl
```

也可用 `uv sync` / `uv run`（本机若 uv trampoline 异常，改用上方 conda 路径）。  
环境变量见 `.env.example`（`DASHSCOPE_API_KEY` 必填；本地演示默认端口 **8001**）。

### Docker Compose

```powershell
docker compose up --build
# API: http://localhost:8000  ·  UI: http://localhost:8501
```

容器化实跑（2026-09-14，Docker 29.7.2 + Compose v5.5.1，WSL2，已实测）：

1. `docker compose up --build` → api/ui 两容器就绪，`GET /health` 200。
2. 三条演示路径（真实 Provider，`DASHSCOPE_API_KEY` 由 compose 从 `.env` 注入）：
   - 可回答：`POST /api/v1/questions {"question":"员工迟到会怎么处理？"}` → `ANSWERED` + 引用（约 4.9s）
   - 无证据：`{"question":"今天北京的天气怎么样？"}` → `NO_EVIDENCE`，answer 空（约 3.5s）
   - 冲突：`{"question":"员工年假到底是几天？"}` → `CONFLICT` + 两份依据（约 6.0s）
3. 引用回看：`GET /api/v1/documents/{id}/source?page=N` → 200（`application/pdf`）。

证据：`artifacts/smoke/step17-compose-e2e.md`。

## 评测

固定评测集 `evaluation/cases/phase1.jsonl`（22 条，含可答/不可答/冲突样本）。金标使用稳定的
「文档引用 + 页码 + 原文短语」，不使用 evidence_id（切片参数改变会导致 ID 漂移）。指标在适用样本上
计算，无法计算返回 `NOT_APPLICABLE`（不记 0/PASS）。

| 指标 | 适用样本 |
| --- | --- |
| Recall@K | answerable=true |
| 引用正确率 | ANSWERED/CONFLICT |
| 忠实度（轻量规则式） | ANSWERED |
| 答案正确率 | 有人工参考答案 |
| 拒答率 | 全部 |
| 冲突准确率 | 冲突 + 相邻非冲突 |

## 质量门禁

`.github/workflows/ci.yml` 执行（SPEC §11.2）：

| 检查 | 命令 |
| --- | --- |
| 分层依赖 | `lint-imports --config importlinter.ini` |
| 旧 CASE 防线 | `python tools/legacy_guard.py check-refs`（本地另跑 `verify`） |
| 静态检查 | `ruff check .` |
| 类型检查 | `mypy`（`--strict`） |
| 测试 | `pytest tests/unit tests/contract tests/smoke` |
| 密钥扫描 | grep 零硬编码密钥 |
| 依赖安全 | `pip-audit` |

## 旧 CASE 只读防线

仓库根 `06_*` ~ `10_*` 为原始学习案例（只读、不跟踪、不修改）。完整性由
`tools/legacy_guard.py` + `tools/legacy_manifest.json` 保证：

```powershell
python tools/legacy_guard.py verify      # 基线校验（本地，零漂移）
python tools/legacy_guard.py check-refs  # 新源码运行时引用检查
python tools/legacy_guard.py gen         # 重新生成基线
```

## 文档

- 唯一事实来源：`.docs/SPEC.md`
- 开发契约：`.docs/SPEC.md` §11
