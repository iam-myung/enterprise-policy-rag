# 企业内部制度知识库问答系统技术规格（SPEC）

| 属性 | 内容 |
| --- | --- |
| 版本 | v0.1 Draft |
| 对应 PRD | `PRD.md` v1.0 |
| 项目规模 | S 级个人独立开发项目 |
| 架构形态 | Python 单栈、模块化单体、Clean Architecture |
| 当前交付范围 | Phase 1 MVP |
| 文档状态 | 待用户确认；确认后才生成 Prompt-Step 与进入实现 |

## 0. 架构结论

### 0.1 产品与用户旅程确认

**产品摘要：** 面向新员工的企业制度问答系统，从考勤、请假、报销制度 PDF 中检索证据，生成可回看原文且能在证据不足时拒答的答案。

**核心旅程：** 制度维护者导入 PDF → 系统解析、切片并建立索引 → 新员工输入问题 → 系统混合检索、重排并生成答案 → 用户核对文件名、版本、页码和原文片段 → 项目维护者使用固定测试集评测。

**Phase 1 IN：** 制度文档导入与解析、带引用制度问答、基线与目标方案评测。

**Phase 1 OUT：** 登录、RBAC、部门隔离、审批流、在线编辑、多租户、多知识库协同、用户反馈系统、移动端、复杂数据看板、扫描件 OCR 保证、Phase 2 健康度与版本对比功能。

### 0.2 规模与单栈决策

- 选择 **S 级**：3 个 P0、单人开发、本地可交互 Demo，不满足拆微服务条件。
- 选择 **Python 单栈**：FastAPI、Streamlit、Pydantic、SQLite、FAISS、BM25 与 Qwen/DashScope 均在一个仓库、一个领域模型和一套测试体系内。
- FastAPI 与 Streamlit 是同一模块化单体的两个入口，不是两个独立业务服务；不得复制业务逻辑。
- 不引入消息队列、Redis、PostgreSQL、Kubernetes、微服务、Agent 编排或对话记忆。
- S 级只产出本 `SPEC.md`；API 合约与简版架构内嵌，不额外创建 `API.md` 或 `ARCHITECTURE.md`。

### 0.3 关键技术决策

| 领域 | 决策 | 原因 |
| --- | --- | --- |
| Web API | FastAPI + Pydantic | Python AI 生态一致，提供明确的校验与 OpenAPI。 |
| Demo UI | Streamlit | 低成本完成可交互 Demo；UI 只调用 API。 |
| 元数据 | SQLite + SQLAlchemy + Alembic | 单机可运行、可迁移、无需外部服务。 |
| PDF 解析 | `DocumentParserPort` + MinerU 适配器 | 保留复杂 PDF 解析能力，同时隔离供应商与 I/O。 |
| 文本切片 | Application 内的确定性页内切片策略 | 确保引用可定位；它是纯业务算法，不建立多余 Port，Phase 1 不启用 LLM 语义切片。 |
| 稠密检索 | DashScope Embedding + FAISS | 复用已学习能力，适合本地小规模语料。 |
| 稀疏检索 | BM25 + 中文分词 | 补足制度编号、专有词和精确关键词召回。 |
| 融合 | Application 内的 Reciprocal Rank Fusion（RRF）纯函数 | 避免直接混合不同分值尺度，不建立多余 Port。 |
| 重排 | `RerankerPort` + Qwen 结构化重排适配器 | 目标方案使用；失败时允许退化为 RRF 排序。 |
| 回答生成 | `ChatModelPort` + Qwen/DashScope 适配器 | 模型可替换；输出必须通过 Pydantic 与引用校验。 |
| 评测 | 固定 JSONL 数据集 + Recall@K + 轻量规则式忠实度（Phase 1 不引入 RAGAS）+ 人工抽检 | 同时验证检索、忠实度、引用和拒答。 |
| 部署 | Docker Compose 本地演示 | 复现成本低，API/UI 仍共享一个代码仓库。 |

## 1. 新旧工程物理隔离

### 1.1 只读参考区

项目根目录中的以下目录是**原始学习案例，只读且不属于新系统运行时**：

```text
06_基座_RAG-企业知识库-实战版/
07_可吸收_CASE1-知识库处理场景/
08_可吸收_ragas-demo/
09_可吸收_CASE-切片策略/
10_可吸收_CASE-ChatPDF-Faiss/
```

约束如下：

1. 禁止修改、重命名、移动、格式化或删除上述目录中的任何文件。
2. 禁止在上述目录生成 `.env`、虚拟环境、缓存、索引、日志、评测结果或临时文件。
3. 新工程禁止通过 `sys.path`、相对导入、动态加载、软链接或复制粘贴后保留原模块依赖来执行旧 CASE。
4. 旧 CASE 只允许人工阅读和提炼设计思路；新实现必须使用新命名、新契约和新测试独立完成。
5. Step 0 在首次实现前生成 `tools/legacy_manifest.json`，记录每个旧文件的相对路径、大小与 SHA-256；本地 pre-commit 重新计算并阻断任何漂移。
6. 新项目 Git 仓库跟踪 `.docs/`（PRD/SPEC）、根 `.gitignore`、应用代码（仓库根下的 `src/`、`tests/`、`tools/`、配置与 Docker 等）；旧 CASE 不复制、不发布到新的项目仓库，CI 只检查新代码不存在旧目录名、旧模块或越界路径引用。
7. `tools/legacy_guard.py` 同时执行“本地 hash 基线检查”和“新源码运行时引用检查”；CI 环境没有旧 CASE 时只执行后者，不将缺少外部参考目录误判为通过了 hash 检查。
8. 任何需要保存的中间产物只能进入仓库根的 `workspace/` 或 `artifacts/`。

### 1.2 仓库根 = 应用工程根

所有新应用代码与运行产物统一放在**仓库根目录**（与 `.docs/`、`.cursor/` 同级）。Python 包名仍为 `enterprise_policy_rag`（位于 `src/enterprise_policy_rag/`）。

```text
<repo-root>/
├─ .docs/                 # PRD / SPEC / Prompt-Step
├─ .cursor/               # Agent 规则
├─ .github/               # CI
├─ src/enterprise_policy_rag/   # 应用包
├─ tests/
├─ tools/
├─ pyproject.toml
└─ …
```

Step 0 在仓库根初始化 Git；根 `.gitignore` 明确排除五个旧 CASE 目录，旧 CASE 不移动进 Git 跟踪范围，也不在旧 CASE 内创建子目录。旧 CASE 的完整性由本地 SHA-256 manifest 负责，而不是依赖 Git 追踪。

### 1.3 旧 CASE 能力吸收矩阵

| 只读来源 | 可吸收的设计思路 | 明确不继承 |
| --- | --- | --- |
| `06_基座_RAG-企业知识库-实战版` | PDF 解析、页码保留、FAISS、LLM 重排、结构化回答与 Streamlit 流程 | 财报/公司路由、竞赛输出格式、旧 Prompt、旧目录结构、密钥文件、无测试实现。其 `HybridRetriever` 实际是“向量检索 + LLM 重排”，不是 BM25 混合检索。 |
| `07_可吸收_CASE1-知识库处理场景` | 问题生成、健康度、版本比较与回归评测思路 | Notebook 内存态实现、迪士尼数据、Phase 2 功能的提前实现。 |
| `08_可吸收_ragas-demo` | 参考答案、contexts 与 RAGAS 指标组织方式 | 旧版/弃用 API、代理环境修改、银行原数据和直接运行脚本。 |
| `09_可吸收_CASE-切片策略` | 固定、句界、层次、滑窗、自适应等策略的对比维度 | 同时实现六套生产策略、LLM 语义切片和仅按长度判断质量。 |
| `10_可吸收_CASE-ChatPDF-Faiss` | 页码映射、向量检索与原文回看概念 | 不可信 pickle 反序列化、基于字符累加的脆弱页码推断、银行原数据。 |

吸收矩阵只说明设计来源，不构成代码复用或实现完成证据；新项目的每项能力必须由新合同、新测试与新运行证据独立证明。

## 2. 静态分层架构

```text
[Streamlit UI]       [FastAPI]       [Evaluation CLI]
       \                 |                 /
        +-------- [Interface Layer] ------+
                         |
                  DTO validation only
                         |
                [Application Layer]
       IngestPolicy / AskPolicy / EvaluateRag
                         |
          Domain entities + explicit Ports
                         |
                   [Domain Core]
   policy version rules / citation rules / Result / ErrorCode
                         ^
                         |
                  Port implementations
                         |
                  [Adapter Layer]
  MinerU | Chunker | FAISS | BM25 | DashScope | SQLite | Telemetry
                         |
              [Local Workspace / Providers]
```

### 2.1 允许的依赖方向

```text
interfaces  → application → domain
adapters    → application → domain
composition → interfaces + application + adapters
domain      → Python standard library only
```

- `domain` 禁止导入 FastAPI、Streamlit、Pydantic、SQLAlchemy、FAISS、DashScope、MinerU 或任何网络/数据库库。
- `application` 只能依赖 `domain`、自身 DTO 与抽象 Ports，不得导入具体适配器。
- `interfaces` 负责传输与展示，不得访问数据库、向量索引或模型客户端。
- `adapters` 实现 Ports，捕获基础设施异常并映射为安全错误。
- `composition.py` 是唯一装配入口；禁止全局可变单例和隐式客户端初始化。

### 2.2 模块所有权

| 模块 | 唯一职责 | 可依赖 | 禁止承担 |
| --- | --- | --- | --- |
| `domain` | 制度状态、版本选择、引用有效性、统一结果与错误码 | 标准库 | I/O、框架、数据库、模型调用 |
| `application.ingestion` | 编排文件读取、解析、页内切片、索引和原子发布 | Domain + Ports | SQL、HTTP、Provider SDK |
| `application.qa` | 编排稠密/稀疏检索、RRF、冲突判断、回答生成和引用验证 | Domain + Ports | UI 渲染、模型 SDK 细节 |
| `application.evaluation` | 运行基线/目标方案并汇总指标 | Domain + Ports | 修改生产索引、伪造标注 |
| `adapters.persistence` | SQLite 持久化与事务 | Ports + SQLAlchemy | 业务规则 |
| `adapters.document` | PDF 校验与 MinerU 解析 | DocumentParserPort | 决定制度是否有效 |
| `adapters.retrieval` | FAISS、BM25 和模型重排实现 | Retrieval Ports | 页内切片、RRF 纯规则、最终回答 |
| `adapters.llm` | Embedding、Qwen 重排与回答客户端 | AI Ports | 直接写数据库/UI |
| `interfaces.api` | HTTP 校验、状态码、Envelope 映射 | Application | 业务逻辑、直接 I/O |
| `interfaces.ui` | 输入、答案、引用和错误展示 | API client | 直接调用模型/索引 |
| `interfaces.cli` | 导入与评测命令入口 | Application | 复制业务流程 |
| `adapters.telemetry` | 日志、Span、指标实现 | TelemetryPort | 记录原文、密钥或 PII |

## 3. 仓库目录结构

```text
<repo-root>/
├─ .docs/
├─ .cursor/
├─ .github/
├─ pyproject.toml
├─ uv.lock
├─ README.md
├─ .env.example
├─ .gitignore
├─ importlinter.ini
├─ alembic.ini
├─ docker-compose.yml
├─ Dockerfile
├─ src/
│  └─ enterprise_policy_rag/
│     ├─ domain/
│     │  ├─ entities.py
│     │  ├─ value_objects.py
│     │  ├─ policy_rules.py
│     │  ├─ citation_rules.py
│     │  ├─ result.py
│     │  └─ errors.py
│     ├─ application/
│     │  ├─ contracts/
│     │  │  ├─ documents.py
│     │  │  ├─ questions.py
│     │  │  └─ evaluations.py
│     │  ├─ ports/
│     │  │  ├─ repositories.py
│     │  │  ├─ document_parser.py
│     │  │  ├─ retrieval.py
│     │  │  ├─ models.py
│     │  │  └─ telemetry.py
│     │  ├─ ingestion/
│     │  │  ├─ ingest_policy.py
│     │  │  └─ chunk_pages.py
│     │  ├─ qa/
│     │  │  ├─ ask_policy.py
│     │  │  └─ rrf_fusion.py
│     │  └─ evaluation/
│     │     └─ evaluate_rag.py
│     ├─ adapters/
│     │  ├─ persistence/
│     │  │  ├─ sqlite_models.py
│     │  │  ├─ document_repository.py
│     │  │  └─ migrations/
│     │  ├─ document/
│     │  │  └─ mineru_parser.py
│     │  ├─ retrieval/
│     │  │  ├─ faiss_index.py
│     │  │  ├─ bm25_index.py
│     │  │  └─ qwen_reranker.py
│     │  ├─ llm/
│     │  │  ├─ dashscope_embeddings.py
│     │  │  └─ qwen_chat_model.py
│     │  └─ telemetry/
│     │     └─ otel_telemetry.py
│     ├─ interfaces/
│     │  ├─ api/
│     │  │  ├─ app.py
│     │  │  ├─ dependencies.py
│     │  │  ├─ documents.py
│     │  │  ├─ questions.py
│     │  │  └─ health.py
│     │  ├─ ui/
│     │  │  ├─ app.py
│     │  │  └─ api_client.py
│     │  └─ cli/
│     │     ├─ ingest.py
│     │     └─ evaluate.py
│     └─ composition.py
├─ tests/
│  ├─ factories/
│  ├─ unit/
│  ├─ contract/
│  ├─ integration/
│  ├─ smoke/
│  └─ architecture/
├─ evaluation/
│  ├─ cases/
│  │  └─ phase1.jsonl
│  └─ rubrics/
├─ data/
│  └─ sample_policies/
├─ workspace/                 # 全部运行产物，Git 忽略
│  ├─ uploads/
│  ├─ parsed/
│  ├─ indexes/
│  └─ database/
├─ artifacts/                 # 可复核评测与演示证据
│  ├─ evaluation/
│  ├─ smoke/
│  └─ demos/
└─ tools/
   ├─ legacy_guard.py
   └─ legacy_manifest.json
```

## 4. 共享领域模型与状态规则

### 4.1 核心类型

| 类型 | 字段 | 不变量 |
| --- | --- | --- |
| `PolicyDocument` | `id, title, version, effective_at, expires_at, scope, source_kind, status, sha256, page_count` | `expires_at` 不得早于 `effective_at`；缺失元数据显式为待确认。 |
| `ParsedPage` | `document_id, page_number, source_text, source_text_sha256` | 保存可引用的规范页文本；页码从 1 开始。 |
| `KnowledgeChunk` | `id, document_id, ordinal, page, char_start, char_end, text, text_sha256, token_count` | Phase 1 不跨页；`text == source_text[char_start:char_end]`；同一文档 ordinal 唯一。 |
| `CorpusSnapshot` | `revision, active_document_ids, index_path, created_at` | 发布后不可变；查询必须绑定一个 revision。 |
| `Evidence` | `evidence_id, chunk_id, document_id, title, version, page, char_start, char_end, quote, page_text_sha256, score` | quote 必须由已保存页文本按字符区间截取，不允许模型生成。 |
| `AnswerResult` | `status, answer, citations, warnings, corpus_revision` | `ANSWERED` 必须有有效引用；`NO_EVIDENCE` 不得包含推测性答案。 |
| `GoldEvidence` | `document_ref, page, quote_contains` | 由人工从制度原文标注，跨切片配置保持稳定。 |
| `EvaluationCase` | `id, question, answerable, conflict_expected, gold_evidence, reference_answer?, tags` | gold evidence 与参考答案由人工复核；不能用被测模型回答反向生成标准。 |

### 4.2 文档状态机

```text
PENDING → PROCESSING → ACTIVE
                    ↘ FAILED

ACTIVE → SUPERSEDED
ACTIVE → EXPIRED
FAILED → PROCESSING       # 仅显式重试
```

- 只有 `ACTIVE` 且元数据已确认的制度进入默认问答语料。
- 新索引构建成功前，旧 `CorpusSnapshot` 继续服务；不得暴露半成品索引。
- 发布时先生成不可变索引目录，再在 SQLite 事务内切换 active revision。
- 查询开始时捕获 `corpus_revision`，该请求全程不得切换快照。
- 同内容 `sha256` 重复导入返回 `DUPLICATE_DOCUMENT`，不得重复建库。
- `corpus_revisions` 是 active revision 的唯一事实来源；文件名、环境变量或进程内全局变量不得充当活动指针。

### 4.3 回答状态

| 状态 | 含义 | UI 行为 |
| --- | --- | --- |
| `ANSWERED` | 有足够且无冲突证据 | 显示答案与引用。 |
| `NO_EVIDENCE` | 没有达到证据阈值 | 显示未找到依据，不调用常识补全。 |
| `CONFLICT` | 多份现行制度证据冲突 | 并列显示相关原文，提示人工确认。 |

`NO_EVIDENCE` 与 `CONFLICT` 是成功处理后的业务状态，不映射为 HTTP 5xx。

### 4.4 冲突判定合同

只有同时满足以下条件才允许返回 `CONFLICT`：

1. 候选证据来自至少两份 `ACTIVE` 制度，且适用范围与问题场景存在交集。
2. `ConflictDetectorPort` 返回两条语义互斥的结构化 claim，每条 claim 都绑定输入中的 evidence ID。
3. 两条 evidence 均通过文档版本、页文本哈希、字符区间和原文子串校验。
4. 两份制度不存在明确的“新版本取代旧版本”关系；存在取代关系时采用有效新版本，不标记冲突。

`ConflictAssessmentDTO` 字段为 `is_conflict, claim_a, claim_b, evidence_ids, reason_code`；`reason_code` 仅允许 `MUTUALLY_EXCLUSIVE_RULES/APPLICABILITY_AMBIGUITY`。Detector 超时或输出不合法时，系统不得继续生成确定性制度结论，返回 Provider 失败 Envelope；固定评测集必须包含至少 3 条人工标注的冲突/非冲突边界样本。

## 5. Ports 与不可变契约

| Port | 输入 | 输出 | 约束 |
| --- | --- | --- | --- |
| `DocumentRepositoryPort` | 文档实体/查询条件 | 不可变文档快照 | 只有适配器访问 SQLite。 |
| `CorpusRevisionRepositoryPort` | revision/manifest 快照 | 当前或指定 `CorpusSnapshot` | 原子切换 active revision；任一时刻最多一个 ACTIVE。 |
| `IngestionRunRepositoryPort` | 运行状态快照 | 运行记录 | 错误上下文必须脱敏。 |
| `DocumentParserPort` | 上传文件快照 | `ParsedDocumentDTO` | 保留页码；不得写旧 CASE。 |
| `DenseIndexPort` | chunks/query | index receipt/evidence candidates | 索引按 corpus revision 隔离。 |
| `SparseIndexPort` | chunks/query | index receipt/evidence candidates | 不反序列化不可信 pickle。 |
| `RerankerPort` | question + candidates | 排序后的 evidence ids | 只能返回已给定 ID。 |
| `ConflictDetectorPort` | question + candidates + metadata | `ConflictAssessmentDTO` | 只能引用输入 evidence ids，不裁决制度优先级。 |
| `ChatModelPort` | question + evidence | `ModelAnswerDTO` | 只能引用已给定 evidence ids。 |
| `EvaluationMetricPort` | cases + results | metric report | 不修改线上索引。 |
| `TelemetryPort` | 结构化事件/span/metric | `None` | 参数脱敏，不记录完整制度原文。 |

页内切片和 RRF 是 Application 层纯函数：前者输入 `tuple[ParsedPage, ...]` 并返回 chunks，后者输入两组不可变候选并返回融合结果；二者不使用 Port。所有 Ports 返回 `OperationEnvelope[T]` 或不可变 DTO，不抛出跨层可见的 SDK/驱动异常。

## 6. 统一 Envelope 与错误分类

### 6.1 响应互斥规则

成功响应：

```json
{
  "success": true,
  "data": {},
  "error": null,
  "message": "ok",
  "trace_id": "uuid"
}
```

失败响应：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "sanitized message",
    "context": {}
  },
  "message": "request failed",
  "trace_id": "uuid"
}
```

不变量：

- `success=true` 时 `data` 非空且 `error=null`。
- `success=false` 时 `data=null` 且 `error` 非空。
- `context` 只能包含白名单字段，不得包含密钥、令牌、绝对路径、完整原文、堆栈或未脱敏个人信息。
- 原始异常只进入内部 ERROR 日志；UI 与 API 仅接收标准错误码和安全消息。

### 6.2 ErrorCode

| 分类 | ErrorCode | HTTP | 触发条件 |
| --- | --- | --- | --- |
| 输入 | `VALIDATION_ERROR` | 422 | 字段格式或长度非法。 |
| 文件 | `UNSUPPORTED_FILE_TYPE` | 415 | 非 PDF 或魔数不匹配。 |
| 文件 | `FILE_TOO_LARGE` | 413 | 超过配置上限。 |
| 文档 | `DOCUMENT_METADATA_REQUIRED` | 422 | 必填制度元数据缺失。 |
| 文档 | `DUPLICATE_DOCUMENT` | 409 | 相同 sha256 已存在。 |
| 文档 | `DOCUMENT_NOT_FOUND` | 404 | 文档不存在。 |
| 文档 | `DOCUMENT_NOT_READY` | 409 | 状态不可查询。 |
| 解析 | `DOCUMENT_PARSE_FAILED` | 422 | PDF 可读但解析失败。 |
| 索引 | `INDEX_BUILD_FAILED` | 500 | 新 revision 构建失败。 |
| Provider | `EMBEDDING_PROVIDER_ERROR` | 502 | Embedding 服务失败。 |
| Provider | `RERANKER_PROVIDER_ERROR` | 502 | 重排失败且不允许退化。 |
| Provider | `LLM_PROVIDER_ERROR` | 502 | 回答模型失败或超时。 |
| 引用 | `CITATION_VALIDATION_FAILED` | 502 | 模型返回未知 ID 或伪造引用。 |
| 系统 | `INTERNAL_ERROR` | 500 | 未预期基础设施异常。 |

重排失败时允许按配置退化为 RRF，并在成功响应的 `warnings` 中返回 `RERANKER_DEGRADED`；不得把退化伪装为完整目标方案结果，评测报告必须标记。

## 7. 数据模型

### 7.1 SQLite 表

#### `policy_documents`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | TEXT UUID | PK |
| `sha256` | TEXT | UNIQUE, NOT NULL |
| `title` | TEXT | NOT NULL |
| `version` | TEXT | NOT NULL |
| `effective_at` | DATE | NULL 表示待确认 |
| `expires_at` | DATE | NULL |
| `scope` | TEXT | NOT NULL |
| `source_kind` | TEXT | `PUBLIC_SAMPLE` / `DESENSITIZED_SAMPLE` |
| `status` | TEXT | 状态机枚举，NOT NULL |
| `source_relpath` | TEXT | 相对 `workspace/uploads`，禁止绝对路径 |
| `page_count` | INTEGER | `>= 1` 或处理前为 NULL |
| `row_version` | INTEGER | 乐观并发版本，默认 1 |
| `created_at_utc` | DATETIME | NOT NULL |
| `updated_at_utc` | DATETIME | NOT NULL |

#### `knowledge_chunks`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | TEXT UUID | PK |
| `document_id` | TEXT UUID | FK → policy_documents, NOT NULL |
| `corpus_revision` | TEXT | NOT NULL |
| `ordinal` | INTEGER | NOT NULL |
| `page` | INTEGER | `>= 1`，FK → parsed_pages(document_id, page_number) |
| `char_start` | INTEGER | `>= 0` |
| `char_end` | INTEGER | `> char_start` |
| `text` | TEXT | NOT NULL |
| `text_sha256` | TEXT | NOT NULL |
| `token_count` | INTEGER | `> 0` |

唯一约束：`(document_id, corpus_revision, ordinal)`。

#### `parsed_pages`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `document_id` | TEXT UUID | FK → policy_documents, NOT NULL |
| `page_number` | INTEGER | `>= 1` |
| `source_text` | TEXT | NOT NULL |
| `source_text_sha256` | TEXT | NOT NULL |

主键：`(document_id, page_number)`；Phase 1 chunk 只能引用同页字符区间，禁止跨页 chunk。

#### `corpus_revisions`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `revision` | TEXT UUID | PK |
| `status` | TEXT | `BUILDING/ACTIVE/RETIRED/FAILED` |
| `index_relpath` | TEXT | 相对 `workspace/indexes`，NOT NULL |
| `manifest_sha256` | TEXT | NOT NULL |
| `created_at_utc` | DATETIME | NOT NULL |
| `activated_at_utc` | DATETIME | NULL |

SQLite partial unique index：`status='ACTIVE'` 时最多一行；新 revision 激活与旧 revision 变为 `RETIRED` 必须在同一事务完成。

#### `corpus_revision_documents`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `revision` | TEXT UUID | FK → corpus_revisions |
| `document_id` | TEXT UUID | FK → policy_documents |

主键：`(revision, document_id)`；该表是每个不可变语料快照所含制度集合的唯一清单。

#### `ingestion_runs`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | TEXT UUID | PK |
| `document_id` | TEXT UUID | FK, NOT NULL |
| `status` | TEXT | `RUNNING/SUCCEEDED/FAILED` |
| `target_revision` | TEXT | NOT NULL |
| `error_code` | TEXT | NULL 或 ErrorCode |
| `error_context_json` | TEXT | 脱敏 JSON |
| `trace_id` | TEXT UUID | NOT NULL |
| `started_at_utc` | DATETIME | NOT NULL |
| `finished_at_utc` | DATETIME | NULL |

#### `query_runs`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | TEXT UUID | PK |
| `question_sha256` | TEXT | NOT NULL |
| `question_preview` | TEXT | 默认 NULL；仅在显式开启脱敏记录时保存 |
| `answer_status` | TEXT | `ANSWERED/NO_EVIDENCE/CONFLICT/FAILED` |
| `corpus_revision` | TEXT | NOT NULL |
| `citation_ids_json` | TEXT | ID 列表，不保存检索全文 |
| `latency_ms` | INTEGER | NOT NULL |
| `trace_id` | TEXT UUID | NOT NULL |
| `created_at_utc` | DATETIME | NOT NULL |

### 7.2 评测数据与指标适用性

评测样本使用版本控制的 `evaluation/cases/phase1.jsonl`，不与生产查询记录混用；每条样本必须包含人工标注的 `answerable`、`conflict_expected` 和 `gold_evidence`，只有需要评估答案正确性时才填写 `reference_answer`。

| 指标 | 必要标注 | 适用样本 | 失败含义 |
| --- | --- | --- | --- |
| Recall@K | `gold_evidence.document_ref + page` | `answerable=true` | 目标制度页未进入候选。 |
| Citation correctness | `gold_evidence.quote_contains` | `ANSWERED/CONFLICT` | 引用存在但不支持对应结论。 |
| Faithfulness | answer + retrieved contexts | `ANSWERED` | 答案含未被上下文支持的陈述。 |
| Answer correctness | `reference_answer` | 仅有人工参考答案的样本 | 结论与可复核参考答案不一致。 |
| Refusal precision/recall | `answerable` | 全部样本 | 对有答案问题误拒答或对无答案问题编造。 |
| Conflict accuracy | `conflict_expected` + 两组 gold evidence | 冲突与相邻非冲突样本 | 漏报冲突或把版本替代误判为冲突。 |

- Recall@K 与引用正确率是确定性主指标；忠实度（轻量规则式，Phase 1 不引入 RAGAS）/答案指标是辅助指标，版本和模型配置必须锁定并记录。
- 基线与目标方案必须使用同一 corpus revision、同一评测集版本、同一回答模型与同一人工标注。
- `expected_evidence_id` 不作为金标，因为切片参数改变会导致 chunk/evidence ID 漂移；金标使用稳定的文档引用、页码和原文短语。
- 指标无法计算时返回 `NOT_APPLICABLE` 并说明缺少字段，不得记为 0 或 PASS。

### 7.3 迁移策略

- Alembic 是唯一 Schema 变更入口；禁止运行时自动建表或手改生产 SQLite。
- 每个迁移必须有 upgrade、downgrade 和空库/已有数据两类迁移测试。
- 迁移前复制 SQLite 与当前 corpus revision 清单到 `artifacts/backups/`。
- 破坏性迁移必须由人工审核并显式确认；Phase 1 不做自动删除文档。

## 8. 内嵌 API 合约

### 8.1 通用规则

- 前缀：`/api/v1`。
- 鉴权：Phase 1 无登录，仅允许本地演示环境；部署到公网前必须重新进入架构阶段设计鉴权。
- Content-Type：JSON；Phase 1 API 不负责长时 PDF 导入。
- 问题长度：1–1000 字符。
- 所有响应使用统一 Envelope；所有时间使用 UTC ISO 8601。
- 请求生成或透传 `X-Trace-Id`；响应返回同一 trace id。

### 8.2 `GET /health`

- 目的：验证 API、SQLite、当前 corpus snapshot 可读。
- Auth：No。
- 200 data：`{status, database, corpus_revision, active_document_count}`。
- 503：`INTERNAL_ERROR`，不得返回连接串或绝对路径。

### 8.3 `policy-rag ingest` CLI 合约

- 目的：在维护者工作流中执行可能持续数分钟的 PDF 导入，避免占用同步 HTTP 请求。
- Input：`--file` + `--title` + `--version` + `--effective-at?` + `--expires-at?` + `--scope` + `--source-kind`。
- Success stdout：统一成功 Envelope，data 为 `DocumentSummaryDTO {id, title, version, effective_at, expires_at, scope, status, page_count, corpus_revision}`；进程退出码 0。
- Failure stdout/stderr：统一失败 Envelope；业务失败退出码 2，Provider/系统失败退出码 3。
- 错误：`FILE_TOO_LARGE`、`UNSUPPORTED_FILE_TYPE`、`DUPLICATE_DOCUMENT`、`DOCUMENT_METADATA_REQUIRED`、`DOCUMENT_PARSE_FAILED`、`INDEX_BUILD_FAILED`。
- CLI 与未来 API 上传必须调用同一个 `IngestPolicy`，不得复制导入逻辑。
- 失败时不得切换 active corpus revision；临时文件必须清理；强制 10 分钟总 timeout。

### 8.4 `GET /api/v1/documents`

- 目的：展示已导入制度及其状态。
- Auth：No（仅本地）。
- Query：`status?`。
- 200 data：`{items: tuple[DocumentSummaryDTO, ...], corpus_revision}`。
- 错误：422 `VALIDATION_ERROR`；500 `INTERNAL_ERROR`。

### 8.5 `POST /api/v1/questions`

- 目的：基于当前不可变 corpus snapshot 回答制度问题。
- Auth：No。
- Request：`QuestionRequestDTO {question: str, top_k?: int}`；`top_k` 默认 5，范围 1–10。
- 200 data：`QuestionAnswerDTO {status, answer, citations, warnings, corpus_revision, trace_id}`。
- `CitationDTO`：`{evidence_id, document_id, title, version, effective_at, page, quote, char_start, char_end, page_text_sha256, source_url}`。
- `source_url` 必须由 API 根据 document_id 与 page 生成站内相对路径，模型、用户输入和数据库不得提供任意 URL。
- 错误：422 `VALIDATION_ERROR`；502 `EMBEDDING_PROVIDER_ERROR/LLM_PROVIDER_ERROR/CITATION_VALIDATION_FAILED`；500 `INTERNAL_ERROR`。
- `ANSWERED` 时 citations 非空；`NO_EVIDENCE` 时 answer 只能是边界提示；`CONFLICT` 必须满足 4.4 的判定合同并引用两条互斥 claim 的证据。

### 8.6 `GET /api/v1/documents/{document_id}/source`

- 目的：回看引用对应 PDF 页。
- Auth：No（仅本地）。
- Path：`document_id`；Query：`page`，从 1 开始。
- 200：PDF 内容流，并设置安全的 Content-Disposition。
- 错误：404 `DOCUMENT_NOT_FOUND`；409 `DOCUMENT_NOT_READY`；422 `VALIDATION_ERROR`。
- 必须通过 document_id 查数据库中的相对路径；禁止接受用户提交的任意文件路径。

## 9. AI 能力设计

### 9.1 RAG 与记忆决策

| 项目 | 决策 |
| --- | --- |
| RAG | 必须；所有制度答案必须以检索证据为基础。 |
| 对话记忆 | Phase 1 不需要；每个问题独立处理，避免历史污染。 |
| Agent/Tool Calling | 不需要；固定问答管线更可控。 |
| Chain-of-Thought 展示 | 禁止；UI 只展示简明答案、边界状态与证据。 |

### 9.2 检索管线

```text
Question
  → query normalization
  → Dense top 20 + BM25 top 20
  → RRF fusion top 12
  → Qwen rerank top 5
  → evidence threshold + conflict check
  → answer generation
  → citation ID validation + quote substring validation
  → AnswerResult
```

- “纯向量 top 5”作为固定基线；目标方案是 Dense + BM25 + RRF + Rerank。
- RRF、阈值、top-k 必须配置化并写入评测报告，禁止为单个测试问题硬编码。
- 重排器和生成模型只能引用输入候选的 `evidence_id`，不得生成页码或原文。
- 引用 quote 由系统从 chunk 截取，模型只选择 evidence ID。

### 9.3 Prompt 合约

**System 指令包含：** 只依据 Evidence；证据不足则 `NO_EVIDENCE`；冲突则 `CONFLICT`；不得使用外部常识补全制度；不得输出思维链；只能返回给定 evidence IDs。

**输入：** `question`、当前日期、制度元数据、按 ID 编号的 Evidence 列表。

**结构化输出：**

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `status` | enum | `ANSWERED/NO_EVIDENCE/CONFLICT` |
| `answer` | str | 简明；NO_EVIDENCE 不得含推测结论。 |
| `citation_ids` | tuple[str, ...] | 必须是输入 Evidence ID 子集。 |
| `conflict_note` | str/null | 仅 CONFLICT 使用。 |

### 9.4 Token 与超时预算

- 问题：不超过 1000 字符。
- Evidence：默认 5 条，每条建议 300–500 tokens。
- System + schema：目标不超过 800 tokens。
- 回答：目标不超过 500 tokens。
- 单请求总上下文目标不超过 6000 tokens；超出时按排序截断 Evidence，不截断引用元数据。
- Embedding、Rerank、Chat 各自设置 30 秒超时；问答总超时 45 秒。

## 10. 安全、可观测性与性能

### 10.1 文件与秘密安全

- 上传前验证扩展名、MIME、PDF 魔数、大小与解析页数；文件名只作展示，不直接作为磁盘路径。
- 所有路径通过 `Path.resolve()` 后验证仍位于新工程 `workspace/` 白名单下；拒绝 `..`、绝对路径与越界软链接。
- `.env`、密钥、数据库、上传 PDF、索引和日志不得提交 Git。
- 旧 CASE 中发现的任何 API key 格式内容不得复制到新工程；实际密钥必须轮换并只通过环境变量注入。
- 不可信 pickle 禁止加载；BM25 从 SQLite 中的当前 revision chunks 确定性重建。

### 10.2 结构化可观测性

- JSON 日志字段：`timestamp_utc, level, event, trace_id, operation, duration_ms, status, error_code`。
- Span：`document.validate`、`document.parse`、`chunk.create`、`index.build`、`retrieve.dense`、`retrieve.sparse`、`retrieve.fuse`、`rerank`、`answer.generate`、`citation.validate`。
- Metrics：导入成功/失败数、问答状态计数、Provider 失败数、各阶段耗时直方图、候选数、退化次数。
- `DEBUG` 仅本地诊断；`INFO` 记录业务里程碑；`WARN` 记录可恢复退化；`ERROR` 记录需人工处理的故障。
- 高频循环内禁止 INFO 及以上日志；不得记录完整问题、制度全文、Evidence 全文或密钥。

### 10.3 Phase 1 性能基线

在项目声明的开发机、3 份样例 PDF、20 条固定问题集上记录：

| 场景 | 初始门槛 |
| --- | --- |
| 检索（不含外部模型） | P95 ≤ 1.5 秒 |
| 完整问答 | P95 ≤ 20 秒，单次硬超时 45 秒 |
| 3 份/总计 100 页以内制度导入 | ≤ 5 分钟，硬超时 10 分钟 |
| API/UI smoke | 单场景硬超时 60 秒 |
| 内存 | API、UI 与 MinerU 整个进程树分别记录峰值；总峰值初始门槛 ≤ 8 GiB |

首轮实测必须保存硬件、数据规模和 Provider 配置；如门槛不现实，返回架构阶段修订，禁止静默放宽测试。

## 11. Vibe Coding 强制开发契约

### 11.1 八条防线

1. **物理分层：** Domain 纯净、Port/Adapter 反转依赖、import-linter 阻断反向导入；边缘脚本保持扁平，不创建空壳层。
2. **严格 DAG：** 一次只执行一个 Step；当前 Step 只能修改允许文件；禁止提前创建下游实现、占位类和死代码。
3. **RED/GREEN 防洗绿：** RED 与 GREEN 必须是两个独立 Agent 节点或两个独立对话回合；必须先保存真实失败输出，GREEN 不得改测试断言或阈值。
4. **真实运行 Smoke：** 单元测试之外必须运行 API/CLI/Streamlit 的真实宿主冒烟；所有命令有显式 timeout。
5. **统一错误：** Domain/业务错误用 ErrorCode；基础设施异常在 Adapter 被捕获并脱敏；原始堆栈不进入 UI/API。
6. **HITL DoD：** 架构边界、状态迁移、Schema、破坏性写入、LLM 输出校验与阈值变更需要人工审核。
7. **上下文控制：** 每个 Step 开始只重新注入该 Step 对应的 SPEC 条款、3–5 条关键不变量和相关 ErrorCode；不要求展示私密推理过程。
8. **可观测性：** 核心路径缺少 trace、结构化日志或指标即视为未完成。

### 11.2 架构 Fitness Functions

CI 与 pre-commit 必须执行：

- `import-linter`：检查分层依赖和 Domain 禁止依赖。
- `tools/legacy_guard.py`：检查旧 CASE 路径无变更、新代码无运行时引用。
- `ruff`：代码与测试静态检查。
- `mypy --strict`：新源码严格类型检查。
- `pytest`：Unit、Contract、Integration、Smoke 分层执行，全部带 timeout。
- secret scan：零硬编码密钥。
- 依赖安全扫描：零高严重级别漏洞；例外必须有人类书面接受并记录期限。

### 11.3 测试规则

- Domain 核心行覆盖率 `> 90%`、分支覆盖率 `> 80%`。
- Adapter/UI 不用无意义覆盖率凑数，以 Contract、Integration、Smoke 为准。
- 禁止 `assert True`、catch-all 吞断言、修改期望迁就实现、无来源的 magic expected values。
- 测试数据来自具名常量、factory 或 fixture；外部 Provider 在 Unit 中使用 Port fake，在 Integration 中执行受控真实 smoke。
- 每个跨层 Step 必须验证 DTO 序列化、Envelope 互斥、ErrorCode 与 HTTP 映射。
- 用户要求改变阈值、契约、Schema 或模块边界时，必须先修改并确认 SPEC，再改测试与实现。

### 11.4 每个 Step 的标准 7 段循环

```text
1. SDD 动态对齐：读取当前 Step 的 SPEC 范围与禁止项
2. RED：只写测试并运行，保存预期失败证据
3. GREEN：只写满足 RED 的最小实现
4. Host/Runtime Smoke：真实入口、真实序列化、关键外部边界
5. Human Audit：检查范围、架构、状态、LLM Guardrail
6. Contract Regression：运行已完成 Step 的全部相关测试
7. Evidence：保存命令、退出码、关键输出与产物路径
```

GREEN 阶段禁止修改 RED 测试；若发现契约错误，停止 GREEN，返回架构阶段说明原因。

### 11.5 Definition of Done

一个 Step 只有同时满足以下条件才可关闭：

- RED 失败证据真实存在，失败原因正是缺少当前行为。
- GREEN 最小实现通过 Unit 与跨层 Contract 测试。
- 目标 Host/Runtime Smoke 在 timeout 内通过。
- import-linter 与 legacy guard 零违规。
- 已完成 Step 的回归测试无新增失败。
- 静态检查、类型检查、secret scan、高危漏洞扫描通过。
- 核心路径包含结构化日志、trace id 和必要指标。
- 人工审核当前修改文件清单，确认没有越过 Step 边界。
- `.docs/memory.md` 与 `.docs/DEV_LOG.md` 只记录已完成且有证据的事实；这两个文件在新工程初始化 Step 创建。

## 12. 环境变量

只提交 `.env.example` 的变量名和安全说明，不提交值。

| 名称 | 目的 | 默认/要求 |
| --- | --- | --- |
| `APP_ENV` | `development/test/demo` | 必填 |
| `APP_HOST` | API 监听地址 | 本地默认 `127.0.0.1` |
| `APP_PORT` | API 端口 | 本地配置 |
| `DATABASE_URL` | SQLite URL | 指向新工程 workspace |
| `WORKSPACE_ROOT` | 上传、解析、索引根目录 | 必须位于新工程内 |
| `DASHSCOPE_API_KEY` | Embedding/Qwen Provider 密钥 | 必填，禁止日志输出 |
| `EMBEDDING_MODEL` | Embedding 模型名 | 配置化，不写死业务代码 |
| `RERANK_MODEL` | 重排模型名 | 配置化 |
| `CHAT_MODEL` | 回答模型名 | 配置化 |
| `MAX_UPLOAD_MIB` | 上传大小上限 | 默认 20 |
| `RAG_TOP_K` | 最终 Evidence 数 | 默认 5，范围 1–10 |
| `RAG_RRF_K` | RRF 参数 | 评测记录实际值 |
| `RAG_EVIDENCE_THRESHOLD` | 证据阈值 | 首轮基线后冻结 |
| `PROVIDER_TIMEOUT_SECONDS` | 单 Provider 超时 | 默认 30 |
| `REQUEST_TIMEOUT_SECONDS` | 问答总超时 | 默认 45 |
| `STORE_QUERY_PREVIEW` | 是否保存脱敏问题预览 | 默认 false |
| `LOG_LEVEL` | 日志级别 | Demo 默认 INFO |

启动时必须验证环境变量；缺失密钥只允许健康页显示 Provider 未就绪，不得回显密钥内容。

## 13. 部署、备份与回滚

### 13.1 默认部署

- Docker Compose 启动 `api` 与 `ui` 两个进程，二者使用同一版本镜像和同一只读源码。
- SQLite 与 `workspace/` 通过专用 volume 持久化；旧 CASE 目录不挂载到容器。
- UI 只通过容器网络访问 API，不直接读取数据库、文件或 Provider。
- Demo 默认绑定 localhost；未设计鉴权前禁止公网开放。

### 13.2 发布前检查

1. 锁文件可复现安装。
2. Alembic 在数据库副本上 upgrade/downgrade 测试通过。
3. 架构、Unit、Contract、Integration、Smoke、安全扫描全部通过。
4. 20+ 固定问题评测报告生成并记录配置、corpus revision 与数据集版本。
5. 三条演示路径通过：可回答、无依据拒答、制度冲突。

### 13.3 回滚

- 应用回滚：切换到上一已验证镜像版本。
- 数据回滚：恢复发布前 SQLite 备份。
- 索引回滚：将 active corpus revision 指针切回上一不可变索引目录。
- 回滚不得删除新版本数据；确认稳定后再由人工执行清理。

# 第一部分：Phase 1 MVP

## 14. Phase 1 运行边界

### 14.1 允许实现

- 新工程初始化与旧 CASE 只读防线。
- Domain、DTO、Ports、Envelope 与 ErrorCode。
- SQLite 文档元数据、MinerU 解析、页码感知切片。
- FAISS 基线、BM25、RRF、Qwen 重排、Qwen 回答与引用校验。
- FastAPI、Streamlit、评测 CLI、结构化可观测性。
- 三份样例制度、20+ 固定问题、可复核评测与 Demo 证据。

### 14.2 禁止提前实现

- 用户反馈、知识健康度、知识库版本对比 UI。
- 用户账户、权限、部门隔离、审批或公网部署。
- LLM 语义切片、多 Agent、对话历史、缓存层和异步任务队列。
- 扫描件 OCR 质量承诺、Word/Excel/网页等多格式导入。
- Phase 2/3 的表、接口、空类、Feature Flag 或占位代码。

## 15. Phase 1 验收 Gate

Phase 1 仅在以下证据全部存在时通过：

1. 原始 CASE 五个目录相对 Step 0 SHA-256 manifest 零漂移，legacy guard 通过；新源码无旧 CASE 运行时引用。
2. 三份新制度样例成功导入，版本、日期、适用范围、页码可见。
3. 可回答问题返回真实原文子串引用，可从 source endpoint 回看对应页。
4. 无答案问题不生成制度结论；冲突问题并列展示至少两份依据。
5. 纯向量基线与目标方案使用同一数据集完成对比，报告包含 Recall@K、忠实度、引用正确率、拒答率、延迟与退化标记。
6. API、UI、Evaluation CLI 三个真实入口 smoke 通过且未超时。
7. Domain 覆盖率、架构检查、合同测试、静态检查、安全扫描达到 DoD。
8. README、演示截图/录屏、失败案例和测试输出可供评审复核。

# 第二部分：Phase 2/3 完整版候选

## 16. 后续范围

Phase 1 Gate 通过且用户确认真实需求后，才允许回到 PRD/架构阶段评估：

| 阶段 | 候选能力 | 进入条件 |
| --- | --- | --- |
| Phase 2 | 知识库健康度、知识库版本对比、用户有帮助/未解决反馈 | Phase 1 有真实失败样本或维护痛点证据。 |
| Phase 3 | 登录、RBAC、部门隔离、审批、审计、多知识库 | 存在真实企业使用者和明确安全边界。 |

### 16.1 后续架构原则

- Phase 2 优先复用现有 Ports 与 Evaluation 模块，不改变问答核心契约。
- Phase 3 涉及身份、授权、PII、审计或公网部署时，项目至少升级为 M 级，并补充 `API.md`、`ARCHITECTURE.md`、ADR 与部署文档。
- 未经新的 PRD/SPEC 确认，不预建后续表、接口、权限字段或插件体系。

## 17. 开发顺序 DAG（必须置于 SPEC 末尾）

每个 Step 均拆成独立 RED 回合和 GREEN 回合；下一 Step 只能在当前 Step QA Gate 通过后开始。

| Step | 最小交付单元 | 前置 | Owner | 允许输出 | Host/Smoke 证据 |
| --- | --- | --- | --- | --- | --- |
| 0 | 新工程骨架与旧 CASE 只读防线 | SPEC 确认 | System Architect / QA | 新目录、配置、SHA-256 manifest、legacy guard、架构测试 | guard 验证基线零漂移并阻断模拟违规 |
| 1 | Result、ErrorCode 与 Envelope 契约 | 0 | Backend | Domain 类型、Pydantic DTO、合同测试 | 成功/失败互斥序列化 |
| 2 | 制度实体、元数据与状态规则 | 1 | Backend | Domain 规则与单元测试 | 状态迁移、日期边界、重复规则 |
| 3 | SQLite、Corpus Revision 与迁移 | 2 | Backend | Repository Adapter、revision tables、Alembic、合同测试 | 临时 SQLite upgrade/downgrade 与唯一 ACTIVE revision |
| 4 | PDF 文件安全、MinerU 解析与规范页文本 | 2 | LLM Backend | 文件校验、Parser Adapter、ParsedPage DTO | 一份样例 PDF 页数、页文本与 hash 可复核 |
| 5 | 页内切片与制度导入原子发布 | 3,4 | Backend / LLM Backend | 纯切片函数、IngestPolicy、revision receipt | 同输入 hash 一致；失败不切换旧 revision |
| 6 | 纯向量基线索引与检索 | 5 | LLM Backend | Embedding/FAISS Adapter | 固定问题命中 gold evidence 页 |
| 7 | BM25 与 RRF 混合召回 | 5,6 | LLM Backend | BM25 Adapter、RRF 纯函数 | 关键词命中；融合候选只来自两路输入且排序确定 |
| 8 | Qwen 重排与冲突判定 | 7 | LLM Backend | Reranker、ConflictDetector、退化与结构校验 | 真实 Provider smoke；冲突/版本替代边界通过 |
| 9 | 制度问答与稳定引用校验 | 8 | LLM Backend | AskPolicy、Prompt DTO、页 hash/字符区间校验 | answered/no-evidence/conflict 三路径 |
| 10 | 文档、问答与原文 API | 3,5,9 | Backend | FastAPI routes、source endpoint、HTTP 合同 | 真实 API smoke；合法页成功、越界路径拒绝 |
| 11 | Streamlit Demo UI | 10 | Frontend | UI 与 API client | Headless 启动/DOM smoke，显示状态、答案与引用 |
| 12 | 基线对比评测闭环 | 6,7,9 | Data Analyst / QA | 20+ gold cases、Evaluation CLI、指标适用性报告 | 同 revision/数据集/模型生成可复核对比 |
| 13 | 全链路质量门禁与交付证据 | 0–12 | QA / Debug | CI、性能报告、失败案例、Demo 证据 | Docker Compose E2E 与全部 Gate |

```text
SPEC confirmed
      |
   Step 0
      |
   Step 1
      |
   Step 2
     / \
 Step 3 Step 4
     \   /
     Step 5
        |
     Step 6
        |
     Step 7
        |
     Step 8
        |
     Step 9
       / \
 Step 10 Step 12
     |
 Step 11
      \ /
     Step 13
```

**Active Gate：** 当前只允许评审与修改本 SPEC；用户确认后先生成与 Step 0–13 一一对应的 Prompt-Step，再进入 Step 0，禁止直接开始实现。
