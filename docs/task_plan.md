# task_plan.md — DocMind 执行计划

> planning 三件套之一（计划）。配套：`findings.md`（决策）、`progress.md`（流水）、`notes.md`（teach 笔记）。
> 周计划产出后需开发者确认才动工（停机点 2）。

## 当前阶段

- **周次**：W5（DocMind 第 1 周 / 总周期 W5–W10）
- **规格基线**：`specs/001-doc-ingest-pipeline/spec.md`（2026-09-12 澄清完成，质量清单 16/16）
- **在办提案**：`openspec/changes/add-doc-ingest-pipeline`（proposal + specs×3 + design + tasks，`validate --strict` 通过，**35 个任务**）
- **阶段状态**：任务 0 **完成**；周计划 **已由开发者确认（停机点 2 通过）**；任务 1（运行环境）**进行中**

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
| 1 | 运行环境（分层骨架 + compose + 配置系统 + 测试脚手架 + 错误契约） | 🔄 进行中 | 1.2/1.4/1.5/1.6 完成；1.3 容器健康核验中 |
| 2 | JWT + 用户体系 | 未开始 | 注册/登录可用，接口鉴权生效 |
| 3 | 文档上传（含知识库归属）→ Celery 管线 | 未开始 | 10MB PDF 上传不阻塞 API，状态机进度可查 |
| 4 | 失败重试（自动 2 + 手动 3）+ 错误回写 | 未开始 | 坏文件 failed 可重试，超限有提示 |
| 5 | teach：FastAPI / SQLAlchemy / JWT-RBAC / Celery | 未开始 | 笔记入 `notes.md` |

> 任务 1–5 的细化拆解见 `openspec/changes/add-doc-ingest-pipeline/tasks.md`（10 组 / 35 项），本表只保留周级视图。

## 阻塞项

- **无阻塞**：周计划已于 2026-09-12 确认（停机点 2 通过），可连续实施到下一处停机点（新依赖 / 改 DDL / 改 collection schema）
- 已解除：`.env` 缺 `DATABASE_URL` / `REDIS_URL` / `SECRET_KEY` → 按开发默认值补齐（原 7 个模型网关键未改动）
- 已解除：宿主 8000 / 5432 / 6379 端口已被 OneHub 占用 → compose 用独立 project name + 错开端口（pg 5433 / redis 6380 / nginx 8080）

## 下一步

1. 完成 1.3 容器健康核验（api / worker / beat / pg / redis / nginx 全 healthy，Milvus 不启动）
2. 进入第 2 组：SQLAlchemy 模型（5 张表）→ Alembic 迁移（ADR-0001 已批准，不另走停机点）
3. 每完成一组回写 `docs/progress.md` 证据与 tasks.md 勾选；全部完成再 `/opsx:archive`
