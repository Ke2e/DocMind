# task_plan.md — DocMind 执行计划

> planning 三件套之一（计划）。配套：`findings.md`（决策）、`progress.md`（流水）、`notes.md`（teach 笔记）。
> 周计划产出后需开发者确认才动工（停机点 2）。

## 当前阶段

- **周次**：W5（DocMind 第 1 周 / 总周期 W5–W10）
- **规格基线**：`specs/001-doc-ingest-pipeline/spec.md`（2026-09-12 澄清完成，质量清单 16/16）
- **在办提案**：`openspec/changes/add-doc-ingest-pipeline`（proposal + specs×3 + design + tasks，`validate --strict` 通过，32 个任务）
- **阶段状态**：任务 0 **完成**；周计划已产出，**等开发者确认（停机点 2）**后开始任务 1

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
| 1 | 脚手架复用 OneHub 模式 + compose 加 Milvus | 未开始 | 全家桶健康（Milvus 走可选 profile） |
| 2 | JWT + 用户体系 | 未开始 | 注册/登录可用，接口鉴权生效 |
| 3 | 文档上传（含知识库归属）→ Celery 管线 | 未开始 | 10MB PDF 上传不阻塞 API，状态机进度可查 |
| 4 | 失败重试（自动 2 + 手动 3）+ 错误回写 | 未开始 | 坏文件 failed 可重试，超限有提示 |
| 5 | teach：FastAPI / SQLAlchemy / JWT-RBAC / Celery | 未开始 | 笔记入 `notes.md` |

> 任务 1–5 的细化拆解见 `openspec/changes/add-doc-ingest-pipeline/tasks.md`（10 组 / 32 项），本表只保留周级视图。

## 阻塞项

- **周计划待确认**（停机点 2）：`openspec/changes/add-doc-ingest-pipeline/tasks.md` 未确认前不动工
- 环境准备（Docker Desktop / Python 3.12 / Node 20 + pnpm / `.env` 密钥 / 验收语料）由开发者本地完成
- 仓库尚未 git init（在 change 任务 1.1 中处理）

## 下一步

1. 开发者确认周计划（可逐条改 tasks.md）
2. 执行 `/opsx:apply`（或让我按 tasks.md 逐项实施）：先任务 1 起环境，再任务 2/3 落 DDL 与上传
3. 每完成一组任务回写勾选与 `docs/progress.md`，完工后 `/opsx:archive`
