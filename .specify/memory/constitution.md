# DocMind Constitution

> 来源：`docs/PROJECT_CONTEXT.md` 第 8 节（AI 工作规则 / 保护清单 / 禁改清单 / 停机点）。
> 本文件是 spec-kit 各命令（`/speckit.plan`、`/speckit.tasks`、`/speckit.implement`）的治理约束来源，任何与之冲突的实现方案都视为不合规。

## Core Principles

### I. 原生实现优先（保护清单，NON-NEGOTIABLE）

以下部分必须手写实现，禁止替换为现成库或框架链，代码审查中豁免"重复造轮子"类意见：

- 检索管线：分块 / 双路召回 / RRF 融合 / 重排 / 上下文压缩 —— 禁止使用 LangChain 的 RAG 链、禁止 LlamaIndex
- 手写 mini-agent 工具调用循环（`examples/`，零框架）
- 引用对齐校验（答案按句拆分 → 与被引 chunk 做相似度比对）
- 语义缓存（问题向量与缓存集相似度匹配 + LRU 淘汰）

LangGraph 仅允许用于**编排层**（StateGraph 流程控制），节点内部逻辑必须全部手写。

**理由**：这是简历项目，面试卖点是"每一环都讲得清为什么这么做"。用了框架链就讲不清，等于自毁卖点。

### II. 技术栈锁定

后端 Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0(async) + Alembic + PostgreSQL 16 + Milvus 2.x + Celery/Redis + LangGraph；前端 React 18 + TS + Vite + Tailwind + Zustand + EventSource；部署 Docker Compose。

新增依赖属于架构级决策，须先写 ADR 并经开发者批准。

### III. 先跑通再优化，增量留证据

每周是一个可独立验收的增量：先端到端跑通（W6 朴素 RAG），再逐环优化（W7 混合检索 / W8 Agentic / W10 缓存与评估）。

每个验收点必须有**可复现证据**（日志、数据、截图、评测报告），禁止口头"已完成"。

### IV. 测试先行（核心算法）

RRF 融合、引用对齐、语义缓存、mini-agent 循环四类核心算法，必须先写测试再写实现（Red-Green-Refactor）。

### V. 规格驱动，禁止口耳相传式改动（OpenSpec 主线）

规格主线为 **OpenSpec**：功能变更与 RAG 参数迭代都走 `openspec/changes/<change-id>/`（proposal → spec → tasks），已部署的规格真相保存在 `openspec/specs/`。

`specs/001-doc-ingest-pipeline/spec.md` 是 W5 开工时用 spec-kit 产出的**规格基线**（一次性例外），W5 实施期间视为冻结；spec-kit 的 plan / tasks 工具链不再使用（Q1 结论，2026-09-12）。

禁止在未更新规格的情况下直接改代码。

### VI. 可教学性（teach）

每周安排 teach 主题，关键机制必须能回答"为什么这样设计"与"换种做法会怎样"。实现过程中产生的原理性结论沉淀到 `docs/notes.md`。

## Additional Constraints

### 保护清单（见原则 I）与禁改清单

- `.env` 真实密钥不入 git
- `alembic/versions/` 只增不改
- `docs/task_plan.md` 不得虚构进度
- Milvus collection schema 变更须走 spec 提案
- 数据隔离：所有检索与查询必须带用户维度过滤，禁止跨用户数据泄漏；文档与检索另需带知识库维度过滤（见 ADR-0001）

### 质量门禁

- 全程遵守 karpathy-guidelines（简洁、无过度抽象、无投机性泛化）
- 完工流程：webapp-testing 验收 → dev-verify 拿证据 → dev-code-review + ponytail-review（保护清单豁免）→ dev-commit-writer

## Development Workflow

1. 会话开始：读 `AGENTS.md` 与 `docs/task_plan.md` 同步进度
2. 周初：出周计划，**等开发者确认**后动工
3. 核心算法先写测试
4. 完工走质量门禁（见上）

### 停机点（必须停下等人工）

1. spec / 提案产出后 —— 开发者审
2. 周计划产出后 —— 开发者确认
3. 架构级决策（新依赖 / 改 DDL / 改 collection schema）—— 先记 ADR 等批

## Governance

- 本 constitution 优先于任何惯例做法；冲突时以本文件为准
- 修订须写明理由、影响范围与迁移方案，并同步更新 `AGENTS.md`
- 所有 `/speckit.plan` 产出的技术方案必须显式声明与本文件的合规情况（特别是原则 I 与 II）
- 运行时开发指引见 `AGENTS.md`

**Version**: 1.1.0 | **Ratified**: 2026-09-10 | **Last Amended**: 2026-09-12
