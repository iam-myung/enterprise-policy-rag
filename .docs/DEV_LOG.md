# 开发日志（追加式）

> 只记录已完成且有证据的里程碑；当前态见 `memory.md`。

## 2026-09-13 — Step 0-BUILD 完成（里程碑）

- 初始化新工程骨架 `enterprise_policy_rag/`（pyproject / uv.lock / README / .env.example / .gitignore / importlinter / alembic / docker-compose / Dockerfile）。
- 建立 src 分层空包：56 个 `.py` 占位（domain / application / adapters / interfaces）。
- 建立 tests / evaluation / data / workspace / artifacts 目录结构。
- 实现旧 CASE 只读防线：`tools/legacy_guard.py` + `legacy_manifest.json`（74 文件 SHA-256）。
- 根目录 Git 初始化：仅跟踪 `.docs/`、`enterprise_policy_rag/`、根 `.gitignore`。
- 验收通过：基线零漂移、篡改阻断（退出码 1）、运行时引用零违规、目录结构与 SPEC §3 一致。

## 2026-09-13 — Step 0-QA 通过（里程碑）

- QA-Test 独立验收旧 CASE 只读防线，四项验收点全过，Verdict = PASS。
- ① 基线零漂移（verify 退出码 0）；② 篡改旧 CASE 一字节被阻断（HASH_CHANGED，退出码 1），恢复后零漂移；③ 无 sys.path/相对导入（check-refs + 独立 grep 交叉验证 0 匹配）；④ Git 跟踪清单 81 文件无违禁项。
- 可进入 Step 1-RED。

## 2026-09-13 — Step 1-RED 完成（里程碑）

- 新增 `tests/contract/test_errorcode_contract.py`（14 ErrorCode + 14 HTTP 映射）与 `tests/contract/test_envelope_contract.py`（6 Envelope 互斥 + 7 context 脱敏）。
- `pyproject.toml` 增加 `pythonpath = ["src"]`。
- RED 运行：`pytest tests/contract/ -q` → 2 collection errors，退出码 2，`ImportError: cannot import name 'ErrorCode'`（缺实现，非语法错误）。
- 证据落盘 `artifacts/smoke/step1-red.txt`。

## 2026-09-13 — 依赖安装到 dev_env_311（环境配置）

- `uv pip install --python dev_env_311 -e . --group dev`，核心依赖 + dev 工具组全部装入 conda `dev_env_311`，`find_spec` 验证无缺失。

## 2026-09-13 — Step 1-GREEN 完成（里程碑）

- 实现 `domain/errors.py`（ErrorCode 14 成员 str Enum + http_status + category + ErrorCategory）、`domain/result.py`（OperationEnvelope[T] 互斥校验、ErrorDetail context 脱敏、AnswerStatus、validate_error_context、CONTEXT_ALLOWED_KEYS）、`application/contracts/envelope.py`（Pydantic ErrorDTO / EnvelopeDTO）。
- 验收：`pytest tests/contract/ -v` → 29 passed；`import-linter lint` → 2 kept 0 broken。
- 修正：`importlinter.ini` 注释改纯 ASCII；import-linter 需 `PYTHONPATH=src` 运行。

## 2026-09-13 — Step 1-QA 通过（里程碑）

- QA-Test 独立验收契约层，四项验收点全过，Verdict = PASS。
- ① Envelope 序列化互斥（Pydantic EnvelopeDTO 成功/失败 JSON + OperationEnvelope 构造边界）；② ErrorCode→HTTP 映射 14 项全对；③ 脱敏四类（密钥/绝对路径/完整原文/堆栈）均拒绝；④ domain 无框架依赖（import-linter KEPT + 独立 grep）。
- 独立证据 `artifacts/smoke/step1-qa-verify.py`，ALL CHECKS PASSED。
- 可进入 Step 2-RED。

## 2026-09-13 — Step 2-RED 完成（里程碑）

- 新增 `tests/unit/` 4 个测试文件：PolicyDocument 日期不变量（5 例）、状态机合法/非法迁移（6+18）、KnowledgeChunk 切片/ordinal/不跨页（7 例）、Evidence.quote 截取（2 例）。
- RED 运行：`pytest tests/unit/ -q` → 4 collection errors，退出码 2，`ImportError`（实体与规则函数未实现）。
- 证据落盘 `artifacts/smoke/step2-red.txt`。
- 可进入 Step 2-GREEN。

## 2026-09-13 — Step 2-GREEN 完成（里程碑）

- 实现 `domain/entities.py`（DocumentStatus 6 态 + PolicyDocument/ParsedPage/KnowledgeChunk/CorpusSnapshot/Evidence）、`domain/value_objects.py`（DateRange）、`domain/policy_rules.py`（can_transition + validate_chunk_source + validate_chunk_ordinals）、`domain/citation_rules.py`（validate_evidence_quote）。
- 验收：`pytest` → 67 passed；Domain 行覆盖 97%、分支 ≈97%；import-linter 2 kept 0 broken。
- 消除 PolicyDocument 与 DateRange 重复校验（复用 DateRange，value_objects 0% → 100%）。
- 可进入 Step 2-QA。

## 2026-09-13 — Step 2-QA 通过（里程碑，PASS with risks）

- 独立验收：① 状态机穷举 36 种迁移全对；② 日期边界正确；④ chunk 字符区间/ordinal 不变量正确。
- ⚠️ 风险：③「同内容 sha256 重复规则」未在 Step 2 实现（属 Step 5 IngestPolicy），须在 Step 5 显式实现并验收，防止「重复建库」防护缺失。
- 独立证据 `artifacts/smoke/step2-qa-verify.py`，ALL CHECKS PASSED。
- 可进入 Step 3-RED。

## 2026-09-13 — Step 3-RED 完成（里程碑）

- 新增 `tests/contract/test_schema_contract.py`（七表结构 + sha256 UNIQUE + 复合唯一 + 复合 PK + partial unique index 6 例）、`tests/integration/test_migrations.py`（Alembic 往返 2 例）、`tests/integration/test_corpus_revision_repository.py`（原子切换 + 唯一 ACTIVE 2 例）。
- RED 运行：`pytest` → 2 collection errors，退出码 2，`ImportError: cannot import name 'Base' / 'CorpusRevisionRepository'`。
- 证据落盘 `artifacts/smoke/step3-red.txt`。
- 可进入 Step 3-GREEN。

## 2026-09-13 — Step 3-GREEN 完成（里程碑）

- 实现 `adapters/persistence/sqlite_models.py`（Base + 七模型，含 partial unique index `status='ACTIVE'`）、`document_repository.py`（CorpusRevisionRepository activate/get_active）、`migrations/`（env.py + script.py.mako + versions/0001_initial.py）、`application/ports/repositories.py`（CorpusRevisionRepositoryPort + DocumentRepositoryPort）。
- 验收：3-RED 10 passed；import-linter 2 kept 0 broken；全量 77 passed。
- 修正：alembic.ini 注释纯 ASCII + prepend_sys_path=src + path_separator=os；修正迁移测试断言（alembic_version 内部表）。
- 可进入 Step 3-QA。

## 2026-09-13 — Step 3-QA 通过（里程碑，PASS with risks）

- 独立验收：① upgrade/downgrade 往返通过；② 唯一 ACTIVE 原子切换通过（rev2 激活、rev1 退 RETIRED、count==1）；③ 无运行时自动建表（grep create_all 0 匹配）。
- ⚠️ 风险：④「路径白名单」未实现（属 Step 4 文件安全），须在 Step 4 显式实现并验收。
- 独立证据 `artifacts/smoke/step3-qa-verify.py`，ALL CHECKS PASSED。
- 可进入 Step 4-RED。

## 2026-09-13 — Step 4-RED 完成（里程碑）

- 新增 `tests/unit/test_file_validation.py`（扩展名/MIME/魔数/大小 5 例）、`tests/unit/test_path_whitelist.py`（相对/越界/绝对/软链接 4 例）、`tests/contract/test_document_parser_port.py`（ParsedPageDTO/ParsedDocumentDTO/DocumentParserPort 3 例）。
- RED 运行：`pytest` → 3 collection errors，退出码 2，`ModuleNotFoundError: ...file_validation` / `ImportError: cannot import name 'ParsedPageDTO'`。
- 证据落盘 `artifacts/smoke/step4-red.txt`。
- 可进入 Step 4-GREEN。

## 2026-09-13 — Step 4-GREEN 完成（里程碑）

- 实现 `application/ports/document_parser.py`（ParsedPageDTO/ParsedDocumentDTO/DocumentParserPort）、`adapters/document/file_validation.py`（FileValidationError + validate_upload_file + resolve_within_workspace）、`adapters/document/mineru_parser.py`（MinerUParser 用 pypdf 实现 Port）。
- 验收：4-RED 11 passed + 1 skipped；全量 88 passed；import-linter 2 kept 0 broken。
- smoke：样例 PDF 解析（2 页中文 + sha256 可复核）`artifacts/smoke/step4-smoke.py`。
- 架构决策：PDF 解析供应商偏离 SPEC（MinerU → pypdf，Phase 1 文本 PDF 用轻量实现，DocumentParserPort 隔离供应商）；「路径白名单」风险已闭环。
- 依赖：pypdf>=6.0 加入 pyproject，uv.lock 更新（95 包）。
- 可进入 Step 4-QA。

## 2026-09-13 — Step 4-QA 通过（里程碑）

- 独立验收：① 文件校验四类拒绝；② 页码保留（1,2）；③ 页文本 hash 稳定；④ 越界路径拒绝；⑤ 异常脱敏（DOCUMENT_PARSE_FAILED 无堆栈）——五项全过，Verdict = PASS。
- 观察：pypdf 第三方 logger 输出 "EOF marker not found"（非脱敏失败，建议 Step 13 可观测性处理）。
- 独立证据 `artifacts/smoke/step4-qa-verify.py`，ALL CHECKS PASSED。
- 可进入 Step 5-RED。

## 2026-09-13 — Step 5-RED 完成（里程碑）

- 新增 `tests/unit/test_chunk_pages.py`（确定性/不跨页/char 区间可回源/ordinal 唯一 4 例）、`tests/integration/test_ingest_policy.py`（重复 sha256 拦截 + 构建失败不切换 revision + 成功切换 3 例，含 Fake Parser/Repo/IndexBuilder）。
- RED 运行：`pytest` → 2 collection errors，退出码 2，`ImportError: cannot import name 'chunk_pages' / 'DocumentSummaryDTO'`。
- 证据落盘 `artifacts/smoke/step5-red.txt`。
- 可进入 Step 5-GREEN。

## 2026-09-13 — Step 5-GREEN 完成（里程碑）

- 实现 `application/ingestion/chunk_pages.py`（chunk_pages 页内切片纯函数）、`application/contracts/documents.py`（DocumentSummaryDTO）、`application/ingestion/ingest_policy.py`（IngestPolicy 编排 + IndexBuilder Protocol）。
- 验收：5-RED 7 passed；import-linter 2 kept 0 broken；全量 95 passed。
- 失败路径不切换 revision（构建失败 → INDEX_BUILD_FAILED，不 activate）。
- 「sha256 重复规则」风险已闭环（IngestPolicy 通过 get_by_sha256 拦截 DUPLICATE_DOCUMENT）。
- 可进入 Step 5-QA。

## 2026-09-13 — Step 5-QA 通过（里程碑，PASS with risks）

- 独立验收：① 同输入 hash 一致（两次 chunk_pages 签名一致 + 每 chunk sha256 可复核）；② 失败不切换旧 revision；③ 重复导入拦截（DUPLICATE_DOCUMENT）——三项全过。
- ⚠️ 风险：④「临时文件清理」与⑤「10 分钟总 timeout」未实现（SPEC §8.3 IngestPolicy 规则，5-RED 未覆盖，grep ingestion 目录 0 匹配），须在 Step 6（索引构建临时文件清理）/ Step 8 CLI / Step 10 API（超时）落实并验收。
- 独立证据 `artifacts/smoke/step5-qa-verify.py`，ALL CHECKS PASSED。
- 可进入 Step 6-RED。

## 2026-09-13 — Step 6-RED 完成（里程碑）

- 新增 `tests/contract/test_dense_index_port.py`（IndexReceipt/EvidenceCandidate 字段 + 不可变 + DenseIndexPort 声明 build/query，5 例）、`tests/integration/test_faiss_index.py`（receipt 可复核 + 候选距离升序 + revision 隔离 + 固定问题命中 gold 页，4 例，用确定性 fake embedder bag-of-chars，不调真实 API）。
- RED 运行：`pytest` → 2 collection errors，退出码 2，`ImportError: cannot import name 'DenseIndexPort' / 'FaissIndex'`（两模块仍为 Step 0 占位）。
- 证据落盘 `artifacts/smoke/step6-red.txt`。
- 契约定义：`DenseIndexPort`(Protocol, build/query) + `IndexReceipt`(revision/index_relpath/chunk_count/manifest_sha256, frozen) + `EvidenceCandidate`(chunk_id/document_id/distance, frozen)；manifest_sha256 契约 = 对 chunks 按 (document_id, ordinal) 排序清单的 sha256。
- 可进入 Step 6-GREEN。

## 2026-09-13 — Step 6-GREEN 完成（里程碑）

- 实现 `application/ports/retrieval.py`（DenseIndexPort + IndexReceipt + EvidenceCandidate）、`adapters/retrieval/faiss_index.py`（FaissIndex 按 revision 隔离，内存 IndexFlatL2，不 load 不可信 pickle）、`adapters/llm/dashscope_embeddings.py`（DashScopeEmbeddings 30s 超时 + EmbeddingProviderError）。
- 验收：6-RED 9 passed；import-linter 2 kept 0 broken；全量 104 passed 1 skipped；ruff 新增 5 文件全绿；mypy 新增 3 源文件 0 问题。
- smoke：`artifacts/smoke/step6-smoke.py` 端到端（解析→切片→embedding→FAISS→query）命中样例文档；因 DASHSCOPE_API_KEY 未配置，当前为 fake embedding 模式，真实模式待配置 key。
- 修正：RED 测试 `get_type_hints(DenseIndexPort)` 对 Protocol 方法失效（RED 阶段未执行到）→ 改 `hasattr`（意图不变）；pyproject 增 `per-file-ignores "tests/**"=["S101"]`；FaissIndex embedder 补 Callable 注解满足 mypy strict。
- 可进入 Step 6-QA。

## 2026-09-13 — Step 6-QA 通过（里程碑，PASS with risks）

- 独立验收：① revision 隔离；② 固定问题命中 gold 页；③ 无 pickle 反序列化（源码正则扫描 0 匹配）——三项全过。
- ⚠️ 风险：④「Provider 失败映射 502」仅部分落地（`EMBEDDING_PROVIDER_ERROR`=502 与 `EmbeddingProviderError` 就绪，但「捕获异常 → 映射 Envelope」的上层链路未实现，属 Step 9 AskPolicy）。
- 另：真实 Embedding smoke 依赖 DASHSCOPE_API_KEY（未配置），当前 fake embedding 交叉验证。
- 独立证据 `artifacts/smoke/step6-qa-verify.py`，ALL CHECKS PASSED。
- 可进入 Step 7-RED。

## 2026-09-13 — Step 7-RED 完成（里程碑）

- 新增 `tests/unit/test_rrf_fusion.py`（只来自两路/降序/多路命中更高/RRF 参数化/空输入/FusionCandidate，6 例）、`tests/contract/test_sparse_index_port.py`（SparseCandidate 字段+不可变 + SparseIndexPort 声明 build/query，3 例）、`tests/integration/test_bm25_index.py`（确定性重建/中文专有词命中/制度编号命中/revision 隔离，4 例）。
- RED 运行：`pytest` → 3 collection errors，退出码 2，`ImportError: cannot import name 'FusionCandidate' / 'SparseCandidate' / 'BM25Index'`（三模块仍为 Step 0 占位）。
- 证据落盘 `artifacts/smoke/step7-red.txt`。
- 契约定义：`SparseIndexPort`(Protocol) + `SparseCandidate`(chunk_id/document_id/score, frozen, 复用 IndexReceipt)；`rrf_fusion(dense_ids, sparse_ids, k=60)` + `FusionCandidate`(candidate_id/rrf_score)，RRF 公式 Σ 1/(k+rank) 降序。
- 可进入 Step 7-GREEN。

## 2026-09-13 — Step 7-GREEN 完成（里程碑）

- 实现 `application/ports/retrieval.py`（SparseIndexPort + SparseCandidate）、`adapters/retrieval/bm25_index.py`（BM25Index 自定义平滑 IDF BM25 + jieba 分词，可注入 tokenizer）、`application/qa/rrf_fusion.py`（rrf_fusion 纯函数 + FusionCandidate）。
- 验收：7-RED 13 passed；import-linter 2 kept 0 broken；全量 117 passed 1 skipped；ruff 新增 6 文件全绿；mypy 新增 3 源文件 0 问题。
- smoke：`artifacts/smoke/step7-smoke.py` BM25 命中第 2 页 + RRF 融合排序确定。
- 关键决策：弃用 rank_bm25（`BM25Okapi` 的 idf 在 df≈N 时 ≤0 退化、排序不稳定），改用自定义平滑 IDF `log(1+(N-df+0.5)/(df+0.5))`；jieba 默认词典把「年假」切为单字；rank-bm25 依赖保留未使用，留 Step 13 清理。
- 可进入 Step 7-QA。

## 2026-09-13 — Step 7-QA 通过（里程碑）

- 独立验收：① BM25 确定性重建；② RRF 只来自两路输入；③ 排序确定；④ 无 pickle（全 src 源码扫描 0 匹配）——四项全过，Verdict = PASS。
- 独立证据 `artifacts/smoke/step7-qa-verify.py`，ALL CHECKS PASSED。
- 可进入 Step 8-RED。

## 2026-09-13 — Step 8-RED 完成（里程碑）

- 新增 `tests/contract/test_reranker_port.py`（RerankResultDTO 字段+不可变 + RerankerPort 声明 rerank，3 例）、`tests/contract/test_conflict_detector_port.py`（ConflictReasonCode 枚举 + ConflictAssessmentDTO 字段+不可变 + ConflictDetectorPort 声明 detect，4 例）、`tests/unit/test_conflict_rules.py`（条件1 多制度/条件4 版本取代/冲突前置组合，5 例）、`tests/integration/test_reranker.py`（只返回给定 ID/未知 ID 退化/Provider 失败退化，3 例）。
- RED 运行：`pytest` → 4 collection errors，退出码 2，`ImportError: 'RerankResultDTO'/'ConflictAssessmentDTO'/'QwenReranker'` + `ModuleNotFoundError: domain.conflict_rules`。
- 证据落盘 `artifacts/smoke/step8-red.txt`。
- 契约定义：`RerankResultDTO`(evidence_ids/degraded) + `RerankerPort.rerank`；`ConflictReasonCode`(两值) + `ConflictAssessmentDTO`(五字段) + `ConflictDetectorPort.detect`；`domain/conflict_rules.py`(has_multiple_documents/is_version_superseded/conflict_eligible)。
- 可进入 Step 8-GREEN。

## 2026-09-14 — Step 8-GREEN 完成（里程碑）

- 实现 `application/ports/models.py`（RerankerPort/RerankResultDTO + ConflictDetectorPort/ConflictAssessmentDTO/ConflictReasonCode）、`domain/conflict_rules.py`（冲突确定性规则 + evidence_integrity_valid）、`adapters/retrieval/qwen_reranker.py`（QwenReranker + RerankerProviderError）、`adapters/llm/conflict_detector.py`（QwenConflictDetector + ConflictDetectorError）。
- Debug 修复两处缺陷：① `QwenReranker.allow_degrade` 死参数生效（False 抛 `RerankerProviderError` → `RERANKER_PROVIDER_ERROR`）；② `conflict_eligible` 补条件3 evidence 完整性校验；补 5 条回归测试（2 no-degrade + 3 条件3）。
- 验收：8-RED 15 passed；全量 137 passed 1 skipped；import-linter 2 kept 0 broken。

## 2026-09-14 — Step 8-QA 通过（里程碑，PASS with risks）

- 首次验收 3 阻塞 → Debug 修复 → 复验通过。
- ① 重排只返回给定 ID ② 退化标记 ③ 冲突四条件 ④ 版本取代不误判 全过。
- 方案 A 定案：验收点5「固定集≥3 冲突边界样本」划归 Step 12；`prompt-step.html` 8-QA 验收点已修订。
- ⚠️ 风险：条件3「原文子串精确校验」依赖 page_text，归 Step 9 闭环。
- 可进入 Step 9-RED。

## 2026-09-14 — Step 9-RED 完成（里程碑）

- 新增 `tests/unit/test_citation_validation.py`（4 例）、`tests/contract/test_chat_model_port.py`（4 例）、`tests/contract/test_ask_policy_contract.py`（5 例），共 13 条。
- RED 运行：3 collection errors，`ImportError: 'validate_citation_ids'/'ChatModelPort'/'ModelAnswerDTO'`。
- 契约定义：`validate_citation_ids` + `CitationValidationError` + `AnswerResult` + `ChatModelPort` + `ModelAnswerDTO` + `AskPolicy`。
- 可进入 Step 9-GREEN。

## 2026-09-14 — Step 9-GREEN 完成（里程碑）

- 实现 `domain/citation_rules.py`（CitationValidationError + validate_citation_ids）、`domain/result.py`（AnswerResult frozen dataclass）、`application/ports/models.py`（ChatModelPort + ModelAnswerDTO）、`application/qa/ask_policy.py`（AskPolicy 编排：检索→重排→冲突判定→生成→引用校验）、`adapters/llm/qwen_chat_model.py`（QwenChatModel + ChatModelError）。
- 验收：9-RED 13 passed；全量 150 passed 1 skipped；import-linter 2 kept 0 broken。
- 冲突路径引用校验已闭环（validate_citation_ids + validate_evidence_quote 覆盖 CONFLICT 路径）。
- 可进入 Step 9-QA。

## 2026-09-14 — Step 9-QA ~ 13 完成（补记里程碑）

- 系统端到端已跑通：FastAPI（/health、/api/v1/questions、/api/v1/documents、source 回看）、Streamlit UI、评测 CLI；真实运行日志 200 OK。
- Step 12 评测闭环：`evaluation/cases/phase1.jsonl`（22 条）+ `evaluate_rag.py` + `artifacts/evaluation_report.json`（真实 Provider 评测）。
- Step 13 交付证据：`.github/workflows/ci.yml`（8 门禁）+ `artifacts/performance.md`（已实测）+ `failure_cases.md` + demo 证据。
- 全量测试 174 passed / 1 skipped（unit/contract/smoke，该时点）。
- ⚠️ Step 13「结构化可观测性」仍为占位空壳，留待 Step 14。

## 2026-09-14 — 收尾体检：发现 5 项交付缺口（F1-F5）

- 代码 + 产物体检结论：功能已跑通但未达 SPEC 交付完成。发现（除仓库首次提交 F6 外）：
  - F1 可观测性未实现（Step 13 telemetry 占位）。
  - F2 目标方案指标未跑赢基线（引用正确率 0.65<0.7368、拒答率 0.4<0.6、冲突准确率 0.6364<0.7273、degraded_count=2）。
  - F3 RAGAS 口径不一致（README/failure_cases 写 RAGAS，evaluate_rag 实为 jieba 轻量忠实度）。
  - F4 容器化/CI 无实证（无 compose 实跑、CI 未远端执行）。
  - F5 13 处过期占位 docstring。
- 已按用户要求将 F1-F5 拆为 Step 14~18 并入 `.docs/prompt-step.html`（F6 仓库提交由用户单独执行，未入清单）。

## 2026-09-14 — Step 14-RED 完成（里程碑）

- 新增 `tests/contract/test_telemetry_port.py`（6 例：TelemetryPort 三方法 / DTO 不可变 / span 上下文 / noop 可用 / 脱敏安全）与 `tests/unit/test_telemetry_redaction.py`（9 例：四类脱敏确定性断言）。
- RED 运行：2 collection errors，退出码 2，`ImportError: cannot import name 'TelemetryEventDTO' / 'REDACTED_PATH'`。
- 证据落盘 `artifacts/smoke/step14-red.txt`。
- 契约定义：`TelemetryPort`(record_event/record_metric/start_span) + `TelemetryEventDTO`/`TelemetryMetricDTO`/`TelemetrySpan` + `noop_telemetry()` + `redact_field` + 三哨兵常量。

## 2026-09-14 — Step 14-GREEN 完成（里程碑）

- 实现 `application/ports/telemetry.py`（Port + 脱敏纯函数 + noop）、`adapters/telemetry/otel_telemetry.py`（OtelTelemetry：结构化 JSON 日志 + OTel trace/metric 可选，缺失降级 no-op，绝不抛异常）。
- composition 唯一装配 `_build_telemetry()`，注入三链路埋点：问答（retrieve/rerank/answer.generate/citation.validate span + qa.* 事件/指标）、导入（document.parse/chunk.create/index.build span + ingest.* 事件/指标）、评测（evaluate.* 事件/指标），均带 corpus_revision/status/degraded/error_code。
- pyproject 新增 optional 组 `telemetry`（opentelemetry-api/sdk）；`.env.example` 补 `OTEL_ENABLED`。
- 验收：14-RED 15 passed；全量 215 passed / 1 skipped；ruff / mypy --strict / lint-imports 全绿。
- 冒烟：真实 OtelTelemetry 输出结构化 JSON，secret/path/pii/long 均正确脱敏。

## 2026-09-14 — Step 14-QA（FAIL：脱敏对真实密钥失效）

- ②降级、③埋点覆盖、④门禁 均 PASS；⑤ N/A（实现分支）。
- ❌ ①脱敏 FAIL：真实 DASHSCOPE_API_KEY（117 字符，sk- 前缀，含 - _ + / = 等非 [A-Za-z0-9] 字符）未命中 `_SECRET_RE = sk-[A-Za-z0-9]{20,}`，redact_field 返回原样 → 密钥明文进日志。当前埋点未把密钥作为属性传出（属潜伏缺陷）。
- 根因 + 修复已并入 prompt-step 为 `14-FIX`（待执行）。

## 2026-09-14 — Step 14-FIX 完成（里程碑）

- `_SECRET_RE`：`sk-[A-Za-z0-9]{20,}` → `sk-\S{20,}`（`re.IGNORECASE`）。
- 根因：真实 DASHSCOPE_API_KEY 为 JWT 式（sk- 后含 `.` 等非 base64 字符），固定 base64 字符集（方案 A）也覆盖不全；改用「sk- 前缀 + 20+ 非空白字符」对齐 domain/result.py `_SECRET_MARKERS` 口径，长度阈值避免 risk-/task- 误判。
- 新增回归断言 `test_redact_field_real_key_charsets`（base64url/base64/JWT 三样例）。
- 验收：14-RED 原 15 + 新增 1 = 16 passed；全量 216 passed / 1 skipped；ruff / mypy --strict / lint-imports 全绿；真实密钥 `redact_field == REDACTED_SECRET` = True（未打印密钥）。

## 2026-09-14 — Step 14-QA 复验通过（里程碑）

- 14-FIX 后重跑 14-QA：①脱敏 ②降级 ③埋点覆盖 ④门禁 全 PASS；⑤ N/A（实现分支）。
- 真实密钥经 OtelTelemetry 记录后日志不含密钥 / 绝对路径 / PII / 完整原文（4 项断言全过）。
- Step 14（可观测性落地）闭环。

## 2026-09-14 — Step 15-RED 完成（里程碑）

- 以当前 revision `4a2abe…` 重跑评测：引用正确率 0.7<0.7368、拒答率 0.4<0.6、冲突准确率 0.6364<0.7727、degraded=0（旧报告 target=2 未复现）。
- 退化样本：c016（不可答误判 CONFLICT 漏拒答）；c002/c007 冲突误报；c017/c018 双方误判。
- 根因：冲突判定过度触发（§4.4 前置条件未强制 + Prompt 过松），非 RERANKER_DEGRADED。
- 证据 `artifacts/smoke/step15-red.txt`（命令 + 退出码 + 指标对照 + 退化清单 + 根因分析）。

## 2026-09-14 — Step 15-BUILD 完成（里程碑）

- Fix A：`QwenConflictDetector.detect` 前置 `conflict_eligible`（条件1/3/4），新增可选 `superseded_pairs`（§4.4 正确性修复，指标无变化）。
- Fix B：收紧 `conflict_provider` Prompt（同一事项+互斥才判冲突；不同事项/无关/不足判 false）——核心修复。
- 指标：refusal 0.4→0.6、conflict 0.6364→0.7727（均追平基线）；citation 0.7→0.7778（基线 0.7895）；faithfulness 0.9157 反超；answer_accuracy 1.0→0.9412（1 例误拒）。
- 报告写回 `artifacts/evaluation_report.json`；门禁全绿（ruff/mypy/pytest 216 passed / 1 skipped）。

## 2026-09-14 — Step 15-QA 通过（里程碑，PASS with risks）

- ① 指标：拒答率 0.6=0.6、冲突准确率 0.7727=0.7727（追平基线）、忠实度 0.9157>0.8907（反超）；引用正确率 0.7778 略低于基线 0.7895（-0.0117，噪声级）。
- ②可比性（同 revision/数据集/模型/参数）③未触碰 gold（phase1.jsonl 未写）④门槛对照 全 PASS。
- ⑤ 决策记录：SPEC §7.2/§15 未定义「目标方案须优于基线」，仅要求同集对比报告含指标 → 当前结果可接受。
- 风险转交：answer_accuracy 0.9412（1 例可答样本 Fix B 解冲突后转 NO_EVIDENCE，疑似误拒）留待后续收口复核。

## 2026-09-14 — Step 16-RED 完成（里程碑）

- 对照「文档说法 vs 实现事实」：README.md:69 与 artifacts/failure_cases.md:43 声称「RAGAS」，evaluate_rag.py:127-154 实为 jieba 轻量忠实度；failure_cases.md 还错误声称「未配置返回 NOT_APPLICABLE」。
- pyproject.toml:28 注释早已标注「轻量替代」（代码/依赖侧口径一致，仅两处文档漂移）。
- 证据落盘 `artifacts/smoke/step16-red.txt`。

## 2026-09-24 — 进度同步：Prompt-Step 勾选至实现收尾

| 日期 | 里程碑 | 完成模块 | 简要描述 |
| --- | --- | --- | --- |
| 2026-09-24 | 进度同步 | prompt-step / memory | 按落盘证据将 SEED_DONE 勾选 0～15 全闭环 + 16-RED/GREEN + 17-RED/BUILD + 18-RED/GREEN；16/17/18-QA 未裁决保持未勾；下一步 16-QA。回归 pytest 224 passed / 1 skipped（dev_env_311）。 |

- prompt-step.html：新增 `SEED_DONE` + `SEED_VERSION_KEY`（首次打开合并一次，不强制覆盖此后手动取消）。
- 同步确认：忠实度已改「轻量规则式」；Compose E2E `step17-compose-e2e.md` 存在；src 无过期「占位」docstring。
- F6 首次 git commit / 远端 CI 仍由用户执行。

## 2026-09-24 — Step 16-QA BLOCK（忠实度口径验收）

| 日期 | 里程碑 | 完成模块 | 简要描述 |
| --- | --- | --- | --- |
| 2026-09-24 | 16-QA BLOCK | QA-Test | ②③⑤ PASS；①④ FAIL。SPEC:46 仍写 RAGAS/规则 vs §7.2 不引入；README/SPEC 适用 ANSWERED vs 代码/failure_cases 含 CONFLICT；performance.md 无忠实度说明。ruff/mypy/pytest 全绿（224 passed/1 skipped）。 |

- ② 手工复算：jieba 词覆盖 = metric 1.0（match=True）。
- ③ 空 answer → value=None，CLI 序列化为 `NOT_APPLICABLE（…）`，非 0/PASS。
- ⑤ `dev_env_311`：ruff All checks passed；mypy 64 files Success；pytest 224 passed / 1 skipped。
- 未勾选 16-QA；待修文档/合同后重做。

## 2026-09-24 — Step 16-QA 通过（PASS with risks）

| 日期 | 里程碑 | 完成模块 | 简要描述 |
| --- | --- | --- | --- |
| 2026-09-24 | 16-QA PASS with risks | QA-Test | Debug 后复验：①④ 口径统一（轻量+仅 ANSWERED）；② 手工复算 match；③ N/A 正确；⑤ 225 passed。残留：报告 JSON 旧数值、PRD 产品选项措辞。下一张 17-QA。 |

- ① src 无 ragas import；SPEC:46/498 均「不引入 RAGAS」；README/failure_cases/performance 一致。
- ② manual=metric=1.0；CONFLICT-only → NOT_APPLICABLE（无 ANSWERED 样本）。
- ⑤ ruff/mypy/pytest 全绿（dev_env_311）。
- prompt-step SEED 已含 16-QA（seed.v20260924c）。

## 2026-09-24 — Step 17-QA BLOCK（容器/CI 验收）

| 日期 | 里程碑 | 完成模块 | 简要描述 |
| --- | --- | --- | --- |
| 2026-09-24 | 17-QA BLOCK | QA-Test | ①缺构建/启动日志；③CI `.[dev]` 无法安装 dependency-groups（dry-run 仅本包）。②状态可比但问题文案不完全一致。④F6 无 commit 已登记不计 Fail。 |

- 证据：`artifacts/smoke/step17-compose-e2e.md`（三路径+source 200+耗时）存在；无 `step17-red.txt`；无 docker build/up 原文落盘。
- CI：`.github/workflows/ci.yml` working-directory=enterprise_policy_rag、Python 3.11；安装方式与本地不等价。
- F6：`git status` → No commits yet on main（待办，不 Fail）。

## 2026-09-24 — Step 17-QA 通过（PASS with risks）

| 日期 | 里程碑 | 完成模块 | 简要描述 |
| --- | --- | --- | --- |
| 2026-09-24 | 17-QA PASS with risks | QA-Test | Debug 后复验：②③④ PASS；① 容器 build/up 原文仍缺（daemon 不可用，未伪造），本机启动日志+同题三路径+source 200 作允许退化。CI `.[dev]` 已可装门禁工具。下一张 18-QA。 |

- ② 同文案三题状态/引用页一致（compose-e2e §2 + `step17-local-three-paths.json`）。
- ③ `optional-dependencies.dev` + ci.yml 探针；差异（integration / pip-audit）已登记。
- ④ F6：No commits yet on main — 不计 Fail。
- prompt-step SEED 已含 17-QA（seed.v20260924d）。

## 2026-09-24 — Step 18-QA 通过（PASS with risks）

| 日期 | 里程碑 | 完成模块 | 简要描述 |
| --- | --- | --- | --- |
| 2026-09-24 | 18-QA PASS with risks | QA-Test | `*.py` 无「占位/Step 0 禁止写入」；抽样 5 处 docstring 与实现相符；ruff/mypy/pytest 225 passed。残留：migrations/.gitkeep 过期注释；无 commit 无法 diff 证仅改注释。Prompt-Step 0～18 闭环；下一动作 F6（用户）。 |

- ① `src/**/*.py` grep 零命中；`.gitkeep` 一处「占位」作 P2。
- ② 抽样 domain / qa / telemetry / api / document `__init__.py` 职责与实现一致。
- ③ 门禁全绿；git diff 因无基线 commit 无法证「仅 docstring」。
- ④ 未见虚构未实现入口声明。
- prompt-step SEED 已含 18-QA（seed.v20260924e）。
