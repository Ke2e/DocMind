# task_plan.md — DocMind 执行计划

> planning 三件套之一（计划）。配套：`findings.md`（决策）、`progress.md`（流水）、`notes.md`（teach 笔记）。
> 周计划产出后需开发者确认才动工（停机点 2）。

## 当前阶段

- **周次**：W5（DocMind 第 1 周 / 总周期 W5–W10）
- **规格基线**：`specs/001-doc-ingest-pipeline/spec.md`（2026-09-12 澄清完成，质量清单 16/16）
- **在办提案**：`openspec/changes/add-doc-ingest-pipeline`（proposal + specs×3 + design + tasks，`validate --strict` 通过，**35 个任务**）
- **阶段状态**：任务 0、周计划（停机点 2）、ADR-0001 / ADR-0002 / ADR-0003（停机点 3）**均已通过**；
  **第 1 组（运行环境 1.1–1.6）、第 2 组（数据模型与迁移 2.1–2.2）、第 3 组（账号体系 3.1–3.3）、
  第 4 组（知识库 4.1–4.2）、第 5 组（文档上传与受理 5.1–5.5）已完成**；
  `openspec list` → **18/35 tasks**，`openspec validate --strict` → valid；下一项第 6 组（后台处理管线 6.1–6.5）

## 已冻结的规格要点（Q1–Q5）

| 项 | 结论 |
|---|---|
| 规格流程 | OpenSpec 主线（`openspec/changes/` → apply → archive）；spec-kit 仅作 W5 启动文档 |
| 本增量范围 | 解析 → 清洗 → 分块 → 状态可查 → 失败重试；向量化留 002 |
| 数据模型 | `knowledge_bases` 新表 + `documents.kb_id`，按"用户 + 知识库"双过滤（ADR-0001 已批准） |
| 支持格式 | PDF / DOCX / MD / TXT，单文件 ≤ 50MB，无 OCR |
| 失败重试 | 自动 2 次（指数退避）+ 手动至多 3 次 |

## W5 任务清单

| # | 任务 | 状态 | 验收 |
|---|------|------|------|
| 0a | spec-kit 启动文档（spec + clarify + 质量清单） | ✅ 完成 | `specs/001/spec.md` 16/16 通过 |
| 0b | OpenSpec 提案流建立 + W5 change 提案 | ✅ 完成 | `openspec validate --strict` 通过，4/4 构件齐备 |
| 0c | AGENTS.md + constitution + planning 三件套 | ✅ 完成 | constitution v1.1.0；docs 三件套就位 |
| 0d | ADR-0001（knowledge_bases DDL） | ✅ 已批准 | 2026-09-12 批准，随 W5 落地 |
| 0e | ADR-0003（上传传输形态 + python-multipart） | ✅ 已批准 | 2026-09-13 批准，随第 5 组落地（本组唯一新依赖） |
| 1 | 运行环境（分层骨架 + compose + 配置系统 + 测试脚手架 + 错误契约） | ✅ 完成 | 6 容器全 healthy + 经 nginx 真请求 200；配置三档校验（缺必需项即失败）；错误契约 `{code,message,detail?}`；pytest 21 passed |
| 2 | 数据模型与迁移（ADR-0001：5 张表 + Alembic 0001） | ✅ 完成 | 干净库 upgrade→downgrade→upgrade 全通过；`alembic check` 无差异；容器内迁移亦成功 |
| 3 | JWT + 用户体系（账号体系） | ✅ 完成 | 注册 / 登录 / 鉴权依赖就绪；经 nginx 真请求 **11/11 PASS**；pytest **58 passed, 0 skipped** |
| 4 | 知识库（4.1 创建/列表/重命名、4.2 非空拒删） | ✅ 完成 | 4 个接口就绪（`/api/knowledge-bases`）；经 nginx 真请求 **26/26 PASS**（含查库核实）；pytest **93 passed, 0 skipped** |
| 5 | 文档上传与受理（5.1–5.5） | ✅ 完成 | 4 个接口就绪（`/api/documents`）；经 nginx 真请求 **37/37 PASS**（含查库 + 查容器）；**SC-001：10.53MB PDF 0.333s 受理**；pytest **136 passed, 0 skipped** |
| 6 | 后台处理管线（解析 / 清洗 / 分块 6.1–6.5） | 未开始 | 四种格式解析出非空文本；10MB 全流程到完成；`chunk_count` 与片段行数一致 |
| 7 | 状态与进度（7.1–7.2） | 未开始 | 进度单调推进、失败原因可读不泄内部细节 |
| 8 | 失败重试与中断补偿（8.1–8.3） | 未开始 | 坏文件自动重试 2 次后 failed；手动重试回到起点；卡死任务可恢复 |
| 9 | 删除与派生清理（9.1–9.3） | 未开始 | 删除后文档与片段不可查、不计入知识库数量 |
| 10 | 周验收与留档（10.1–10.4） | 未开始 | SC 对照表可追到可复现命令；teach 笔记入 `notes.md` |

> 任务 1–10 的细化拆解见 `openspec/changes/add-doc-ingest-pipeline/tasks.md`（10 组 / 35 项），本表只保留周级视图。

## 阻塞项

- **无阻塞**：可连续实施到下一处停机点（新依赖 / 改 DDL / 改 collection schema）
- 已解除（2026-09-13）：第 5 组的上传接口需要 `python-multipart`（FastAPI 的 `UploadFile`/`Form()` 硬依赖），
  开工实测该包不在 venv 也不在镜像 → **ADR-0003 已批准并落地**（`python-multipart>=0.0.32`）
- 已解除（2026-09-12）：第 3 组的 JWT 签发库与密码哈希库属"新依赖" → **ADR-0002 已批准并落地**（PyJWT 2.14.0 + argon2-cffi 25.1.0，本地与镜像侧均复核）
- 已解除：`.env` 缺 `DATABASE_URL` / `REDIS_URL` / `SECRET_KEY` → 按开发默认值补齐（原 7 个模型网关键未改动）
- 已解除：宿主 8000 / 5432 / 6379 端口已被 OneHub 占用 → compose 用独立 project name + 错开端口（pg 5433 / redis 6380 / nginx 8080）

## 下一步

1. **第 6 组：后台处理管线**（tasks.md 6.1–6.5）—— 解析 → 清洗 → 分块（tiktoken），零新依赖预期
   - `6.1` 要求**先写分块算法测试**（保护清单 TDD）：递归降级顺序、默认 512/64、空文档、超长无标点段落、
     恰好等于粒度、表格密集 → 先失败，再由 `6.2` 原生实现转绿
   - 分块内容忠实性按**三项**校验（覆盖性 / 顺序性 / 忠实性），**不得**用"拼接等于原文"（与 64 token 重叠矛盾）
   - 开发者已点头允许提前做 `6.1`，第 3 / 4 / 5 组期间均未跳步
2. 之后按 tasks.md 顺序：7.x 状态与进度 → 8.x 失败重试与中断补偿 → 9.x 删除清理 → 10.x 验收留档
3. 每完成一组回写 `docs/progress.md` 证据与 tasks.md 勾选；全部完成再 `/opsx:archive`
4. **待办**：`docs/HANDOFF.md` 已刷新到第 5 组完工状态（第 6 次交接）
5. **待开发者表态（第 4 / 5 组审查列出，未擅自改规格）**：
   - 第 4 组：`description` 字段 + PATCH 语义、列表 `document_count` 口径 → 建议回写 `knowledge-base` 规格
   - 第 5 组：状态码 201/415/413 与越权 404、文档响应字段集合（不含 `storage_path`）、扩展名大小写归一 /
     0 字节受理 / 超长文件名被拒 → 建议回写 `document-ingest` 规格（详见 findings D-043）
