# AGENTS.md — DocMind 项目规则

> 面向 AI 的运行时规则。项目原则与治理见 `.specify/memory/constitution.md`，两者冲突以 constitution 为准。
> 开发者：Asize（大三 / 软件工程 / 主力 JS，Python 在学）——讲解要讲清"为什么"，不要只给结论。

## 0. 会话启动顺序（每次必做）

1. 读本文件 + `docs/task_plan.md` 同步进度
2. 读 `openspec/changes/` 下的在办提案；W5 期间另读 `specs/001-doc-ingest-pipeline/spec.md`（冻结基线）与 `clarify-answers.md`
3. 有未回答的澄清问题时，**先问，不要猜**

## 1. 规格驱动流程（OpenSpec 主线）

规格主线为 **OpenSpec**：

```
openspec/changes/<change-id>/proposal.md（为什么改） → spec.md 增量 → tasks.md（怎么做）
```

- 功能变更与 RAG 参数迭代**一律**走 `changes/` 提案流；已部署规格真相在 `openspec/specs/`
- 澄清问题**必须由开发者亲自回答**，禁止代答；代答视为违规
- 架构级方案必须显式声明与 constitution 原则 I（原生实现）、II（技术栈锁定）的合规情况

**例外（一次性）**：`specs/001-doc-ingest-pipeline/spec.md` 是 W5 开工时用 spec-kit 产出的规格基线，W5 期间冻结；`/speckit.plan`、`/speckit.tasks` 不再使用（2026-09-12 Q1 结论）。`.specify/` 与 `.codebuddy/commands/speckit.*` 保留作历史记录，不再驱动开发。

## 2. 保护清单（手写实现，禁止换库，代码审查豁免）

- 检索管线原生实现：分块 / 双路召回 / RRF 融合 / 重排 / 上下文压缩 —— 禁止 LangChain RAG 链、禁止 LlamaIndex
- 手写 mini-agent 工具调用循环（`examples/`，零框架）
- 引用对齐校验自实现
- 语义缓存自实现
- LangGraph 仅限编排层（StateGraph 流程控制），节点逻辑全部手写

**理由**：面试卖点是"每一环讲得清为什么"，用现成链就讲不清。

## 3. 技术栈锁定

Python 3.12 / FastAPI / Pydantic v2 / SQLAlchemy 2.0(async) / Alembic / PostgreSQL 16 / Milvus 2.x / Celery+Redis / LangGraph；前端 React 18 + TS + Vite + Tailwind + Zustand + EventSource；部署 Docker Compose。
新增依赖 = 架构级决策，先写 ADR 等批。

## 4. 质量门禁

- 核心算法（RRF / 引用对齐 / 语义缓存 / mini-agent）先写测试再实现
- 全程 karpathy-guidelines：不过度抽象、不投机性泛化
- 完工：webapp-testing 验收 → dev-verify 拿证据 → dev-code-review + ponytail-review（保护清单豁免）→ dev-commit-writer
- 每个验收点留可复现证据（日志 / 数据 / 截图 / 报告），禁止口头"完成"

## 5. 禁改清单

- `.env` 真实密钥不入 git
- `alembic/versions/` 只增不改
- `docs/task_plan.md` 不虚构进度
- Milvus collection schema 变更走 spec 提案
- 所有检索与查询必须带用户维度过滤

## 6. 停机点（必须停下等人工）

1. spec / 提案产出后 —— 开发者审
2. 周计划产出后 —— 开发者确认
3. 架构级决策（新依赖 / 改 DDL / 改 collection）—— 先记 ADR 等批

## 7. 目录约定

代码与规格直接放在仓库根目录（不再嵌套 `docmind/` 一层）：

```
AGENTS.md  openspec/  backend/  frontend/  docker-compose.yml  docs/  specs/  .specify/
```
