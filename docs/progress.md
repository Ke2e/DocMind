# progress.md — 进度流水

> planning 三件套之一（流水）。只记事实与证据，不虚构进度。

## 2026-09-10

- 读 `docs/PROJECT_CONTEXT.md`，确认 W5（第 1 周）任务 0 为开工项。
- 检测环境：spec-kit CLI v1.0.1 已安装（uv 安装，`~/.local/bin/specify`）。
- 执行 `specify init --here --force --non-interactive --integration codebuddy --ignore-agent-tools`：
  - 生成 `.specify/`（templates / powershell scripts / workflows / memory）
  - 生成 `.codebuddy/commands/speckit.{constitution,specify,clarify,plan,tasks,implement,analyze,checklist,converge,taskstoissues}.md`
  - 未初始化 git（仓库当前非 git repo）
- 撰写 `.specify/memory/constitution.md` v1.0.0（源自 PROJECT_CONTEXT 第 8 节）。
- 创建 `specs/001-doc-ingest-pipeline/`：
  - `spec.md`（按 spec-template 填充，15 条 FR / 4 个 US / 7 条 SC / 12 项边界）
  - `checklists/requirements.md`（16 项中 15 项通过，1 项因待澄清挂起）
  - `clarify-pending.md`（Q1–Q5，**未代答**）
- 创建 `AGENTS.md`（保护清单 / 技术栈 / 质量门禁 / 停机点 / 目录约定）。
- 创建 planning 三件套 `task_plan.md` / `findings.md` / `progress.md`，teach 笔记 `notes.md`。
- **停在停机点 1**：等开发者审 spec 并回答 Q1–Q5。

## 2026-09-12

- 开发者作答 Q1–Q5（未代答）：C / A / B / A / A。记录写入 `specs/001-doc-ingest-pipeline/clarify-answers.md`，原 `clarify-pending.md` 已删除。
- 按答案回填 `spec.md`：
  - 新增 `## Clarifications`（Session 2026-09-12）与「规格归属」章节
  - 新增 User Story 2「用知识库归类文档」(P1) 并重排后续故事编号
  - FR 由 15 条扩到 19 条（新增知识库 CRUD / 归属约束 / 非空库拒绝删除 / 双维度过滤 / 格式与 50MB 上限 / 重名拒绝）
  - Key Entities 增 `Knowledge Base`，Document 增归属知识库；Processing Task 增自动/手动重试计数
  - Success Criteria 由 7 条扩到 9 条；Assumptions 全部去掉"待澄清"标记
- 质量清单 `checklists/requirements.md` 重跑：**16/16 全部通过**。
- constitution 升级 v1.1.0：原则 V 改为 OpenSpec 主线、数据隔离补知识库维度。
- AGENTS.md：§0 启动顺序、§1 流程、§7 目录约定同步为 OpenSpec 主线。
- 新增 `docs/adr/0001-knowledge-base-entity.md`（Proposed，待批）。
- `docs/task_plan.md` / `findings.md` 同步更新（D-006~D-011）。
- 环境探测：`openspec` 命令为残留 shim，模块未安装 → 落地方式待定。
- **停在停机点 3**（ADR 待批）+ OpenSpec 落地方式待定。

## 2026-09-12（续：OpenSpec 落地 + W5 change 提案）

- 纠正探测失误：`openspec --version` 实测 **v1.11.0**（此前误判为"未安装"，原因是沙箱 bash 的 PATH 被清空导致 shim 解析失败）。
- 执行 `openspec init . --tools codebuddy --language zh-CN --no-animation --force`：
  - `openspec/config.yaml`（schema: spec-driven，语言 zh-CN，结构标题与 SHALL/MUST 保留英文）
  - `.codebuddy/commands/opsx/{propose,explore,apply,archive,sync,update}.md` + `.codebuddy/skills/openspec-*`（6 命令 / 6 技能）
  - root `AGENTS.md` 未被改写（diff 无差异，已备份校验）
- `openspec new change add-doc-ingest-pipeline` → 按官方 instructions 逐个生成构件：
  - `proposal.md`（Why / What Changes / Capabilities / Impact；DDL 变更标 BREAKING）
  - `specs/user-auth/spec.md`、`specs/knowledge-base/spec.md`、`specs/document-ingest/spec.md`（ADDED Requirements，含 Purpose）
  - `design.md`（D1–D9 技术决策 + 风险 + 迁移计划 + 开放问题）
  - `tasks.md`（10 组 / 32 项，每项带验证方式）
- 校验：`openspec validate add-doc-ingest-pipeline --strict` → **valid**；`openspec status` → **4/4 构件完成**；`openspec list` → 0/32 tasks。
- ADR-0001 获开发者批准 → ADR 状态改 Approved，spec.md Dependencies 同步。
- `docs/task_plan.md` / `findings.md` 更新（D-011、D-012）。
- **停在停机点 2**：周计划（tasks.md）待开发者确认后 `apply`。

## 2026-09-12（模型与密钥核实）

- 开发者问：`.env` 里的密钥各调用什么模型、DeepSeek 是否有嵌入与重排模型。
- 查官方文档核实：DeepSeek 模型表只有 `deepseek-flash`（V4.1-Flash）与 `deepseek-v4-pro`，**无 embedding / rerank 端点**；嵌入与重排全部走硅基流动（`BAAI/bge-m3` 1024 维 / `BAAI/bge-reranker-v2-m3`，`/v1/embeddings` 与 `/v1/rerank` 共用一个 key）。
- 纠错：修正 `docs/PROJECT_CONTEXT.md` 第 2 节"DeepSeek-V3"（已于官方下线 `deepseek-chat` / `deepseek-reasoner`）→ 现用 `deepseek-flash` / `deepseek-v4-pro`。
- tasks.md 1.4 改为明确写入两个 base_url 与三处模型 ID，并要求可配置覆盖、不写死。
- 复核：`openspec validate --strict` 仍为 valid，0/32 tasks。

## 2026-09-12（配置归位 / git 初始化 / 验收语料 / 交接文档）

- **配置归位**：`.env` 已置于仓库根（compose 与后端共用的单一来源），另建 `.env.example`（占位 + 用途注释，可入库）。
  - 发现实际是**一家统一网关**（一个 BASE_URL + 一个 API_KEY），非两家服务商 → 补 `EMBEDDING_DIM=1024`、`RERANK_BASE_URL`。
- **端点探活（全部实测，非文档推测）**：
  - 生成 `deepseek-v4-pro-0813` → 200；注意默认思考模式，小 `max_tokens` 会返回空 `content`
  - 嵌入 `qwen3.7-text-embedding` → 200，**维度 1024**（与 Milvus 规格一致）
  - 重排 `qwen3.7-text-rerank` → 200，但**只在 DashScope 原生路径**下（`/compatible-mode/v1/rerank` 等均 404）
- **git 初始化**：`git init -b main` + 首次提交 `d34b36b`，43 个文件；
  `.gitignore` 排除 `.env`、`.venv/`、`.codebuddy/`、`.workbuddy/`、`fixtures/acceptance/`，已逐条 `git check-ignore -v` 核验。
- **验收语料**：新增 `tools/gen_acceptance_corpus.py`，生成 10 个文件（含 10.53MB / 114 页大 PDF）。
  pypdf 自检：正常 PDF 可抽文本、扫描件 0 字符、损坏件与错扩展名件报错——均符合预期。
- **交接文档**：`docs/HANDOFF.md`（含环境坑、决策表、工件地图、网关实况、语料结果、建议 skills）。
- `tasks.md` 1.4 由"两家服务商"改写为实际网关配置项；`docs/PROJECT_CONTEXT.md` 模型行同步。
- 复核：`openspec validate --strict` 仍 valid。

## 2026-09-12（停机点 2 通过 + 第 1 组实施）

### 计划确认（开发者本人作答，未代答）

| 待定项 | 结论 |
|---|---|
| 计划增补（1.5 / 1.6 / 5.4 + 顺序与口径修正） | 全部采纳 |
| 宿主端口 | 独立端口：pg 5433 / redis 6380 / nginx 8080 |
| 同一知识库内文档同名 | 允许 |
| 注册密码强度 | ≥8 位且同时包含字母与数字 |

规划件同步修订（`openspec-update-change` 流程）：

- `tasks.md`：32 项 → **35 项**，1.1 带证据勾选
- `specs/user-auth/spec.md`：密码强度阈值写进 Requirement 与场景（否则 3.1 无法客观验收）
- `design.md`：D5 补重叠语义与"覆盖性/顺序性/忠实性"判据、D9 补宿主端口约束、新增 D10（错误契约 + 测试脚手架）
- 复核：`openspec validate add-doc-ingest-pipeline --strict` → **valid**；`openspec list` → **1/35 tasks**

### 环境探测（实测，非推测）

- Docker Desktop 位于 `D:\Docker\App`（非默认路径），CLI 29.7.2 / daemon linux / compose v5.3.1
- 端口冲突：OneHub 占 8000 / 5432 / 6379；既有 Milvus（project `lk_ai`）占 9000-9001 / 9091 / 19530
- 本机无本地 PostgreSQL / psql / curl → HTTP 验证改用 venv 内 httpx
- `.env` 原缺 `DATABASE_URL` / `REDIS_URL` / `SECRET_KEY` → 仅追加缺失键补齐（原 7 行未改），`git check-ignore -v .env` 复核仍忽略

### 任务 1.2 后端分层骨架

- `backend/`：`app/core`（config / errors / db）、`app/api`（deps / routes）、`app/models`（base）、`app/schemas`、`app/services`、`app/workers`，另有 `tests/`、`Dockerfile`、`pyproject.toml`
- Python 3.12.3 虚拟环境 `backend/.venv`（系统解释器 `D:\IDE\Python\Python312`），依赖装齐
- 证据：`uvicorn app.main:app --port 8001` 启动成功（日志 `Application startup complete.`）；`GET /health/live` → 200 `{"status":"ok"}`；`GET /health/ready` → 503（彼时 pg/redis 未起，逐个报不可用）

### 任务 1.3 Docker Compose

- `docker-compose.yml`（project name `docmind`）：api / worker / beat / pg / redis / nginx；Milvus 三件套列在 `milvus` profile，默认不启动
- `docker/nginx.conf`（反代 api，`client_max_body_size 60m` 略大于应用 50MB 上限）、`backend/Dockerfile`、`backend/.dockerignore`
- `backend/app/workers/celery_app.py`：Celery 应用 + beat 心跳调度；`tasks.py`：心跳任务写 `docmind:beat:heartbeat`（TTL = 3 个周期）
- beat 无内置健康端点 → 用「心跳键是否存在」做真探针，实际覆盖 beat → broker → worker → redis 整条链路
- 证据：`docker compose config --quiet` 通过；`docker compose config --services` 为 api/worker/beat/pg/redis/nginx（**不含** Milvus）；加 `--profile milvus` 才出现 milvus-etcd/minio/standalone

### 任务 1.4 配置系统

- `backend/app/core/config.py`：三档配置（必需 3 项 / 占位 7 项 / 业务参数 16 项），业务参数全部可配置且有默认值
- 缺失必需项 → `ConfigError` 并列出缺哪几项；只缺占位项 → 启动并打印告警；模型名与地址全部从配置读
- 证据：`pytest -q` → **11 passed**
- 进程级证据：清空 `DATABASE_URL` / `REDIS_URL` / `SECRET_KEY` 且不读 `.env` 时输出
  `ConfigError -> 配置缺失，应用无法启动：DATABASE_URL、REDIS_URL、SECRET_KEY（读取自 …\.env 或环境变量；请参考 .env.example 补齐）`
- 机器核查：`tests/test_config.py::test_no_hardcoded_model_or_endpoint_in_app_source` 扫描 `backend/app/**/*.py`，禁止出现模型名与服务商地址字面量 → 通过

### 任务 1.5 测试脚手架 / 任务 1.6 错误响应契约

- `tests/conftest.py`：配置隔离（环境变量顶掉 `.env`）、应用与 httpx 客户端 fixture、`raw_client`（容忍应用内异常，用于验 500 响应体）、测试库 schema 建/销毁 fixture（库不可达则 skip 而非假通过）
- `tests/test_health.py`、`tests/test_error_contract.py`、`tests/test_config.py`
- 错误契约证据：框架 404 / 422 / 未捕获异常 / 业务异常四条路径响应体均为 `{code, message, detail?}`；未捕获异常返回 500 且不含 `Traceback` / `site-packages` / SQL 等内部细节

### 第 1 组任务状态

| 任务 | 状态 | 验证证据 |
|---|---|---|
| 1.1 git 初始化 | 完成（前期） | `git log` 3 次提交、工作区干净 |
| 1.2 后端分层骨架 | 完成 | uvicorn 启动 `Application startup complete.`；`/health/live` → 200；pg/redis 未起时 `/health/ready` → 503 并逐项报因，就位后 → 200 |
| 1.3 Docker Compose | **完成** | `docker compose ps` → **6/6 healthy**；`docker ps -a --filter name=docmind-milvus` → **0**；经 nginx `:8080` 打真实请求 `/health/live` → 200、`/health/ready` → 200；beat 心跳键存在、worker 每 30s 消费；OneHub 栈未受影响 |
| 1.4 配置系统 | 完成 | `pytest -q` 11 passed；缺必需项进程级报 `ConfigError`（点名三项）；只缺占位项启动并告警；源码扫描无硬编码模型名与地址 |
| 1.5 测试脚手架 | 完成 | `pytest -q` 可跑通；测试库 schema 建/销毁 fixture 就位（等 2.x 建表后启用）；接口测试不依赖 Celery |
| 1.6 错误响应契约 | 完成 | 404 / 422 / 500 / 业务异常四条路径均返回 `{code, message, detail?}`；500 响应体无内部细节标记词 |

### 第 1 组完成（2026-09-12）

- **1.3 端到端证据（可复现命令）**：
  - `docker compose up -d --build` → `docker compose ps --format 'table {{.Name}}\t{{.State}}\t{{.Health}}'` → api / beat / nginx / pg / redis / worker 六项全 `running healthy`
  - `docker compose config --services`（默认）→ 无 Milvus；`docker compose --profile milvus config --services` → 出现 milvus-etcd / minio / standalone（证明 profile 隔离）
  - 经 nginx 打真实请求（本机无 curl，用 venv 内 httpx）：`GET http://127.0.0.1:8080/health/ready` → `200 {"status":"ok","checks":{"database":null,"redis":null}}`
  - `docker exec docmind-redis redis-cli --scan --pattern 'docmind:beat:*'` → `docmind:beat:heartbeat`；`ttl` → 79；worker 日志每 30s 一条 `Task app.workers.tasks.beat_heartbeat ... succeeded`
- **修掉的两个容器化坑（详见 findings D-023）**：
  - nginx 启动时只解析一次上游主机名，api 容器重建换 IP 后对外持续 502（而 `docker compose ps` 仍报 healthy）→ 改用 Docker 内置 DNS `127.0.0.11` + 变量化 `proxy_pass` 按 TTL 重解析
  - worker / beat 反复重启，根因是 `BEAT_HEARTBEAT_INTERVAL_SECONDS` 字段因同批并行编辑未落盘 → 串行修补并复核
- **新增运行资产**：`docker-compose.yml`、`docker/nginx.conf`、`backend/Dockerfile`、`backend/.dockerignore`、`backend/app/workers/celery_app.py`、`backend/app/workers/tasks.py`

> 待办：1.5 的"双账号 fixture"依赖 `users` 模型，随 3.x 落地补齐（已在 tasks.md 标注依赖关系）。

## 2026-09-12（第 2 组：数据模型与迁移）

### 任务 2.1 五张表模型

- 新增 `backend/app/models/`：`enums.py`（`DocumentStatus` + `STATUS_SEQUENCE` + 两表共用的列类型）、`user.py`、`knowledge_base.py`、`document.py`、`chunk.py`、`processing_task.py`；`__init__.py` 聚合导出（应用与 Alembic 共用一个 `Base`，避免漏注册表导致 autogenerate 生成 DROP）
- 字段口径 = ADR-0001（`name VARCHAR(128)`、`kb_id NOT NULL`、`uq_kb_user_name`、`idx_documents_kb`）+ Key Entities（FR-018 的 8 个文档字段、Processing Task 的两个计数器与最近执行时间）
- 两处新增/取舍（详见 findings D-024 / D-025）：
  - `documents.deleted_at` 墓碑列，落地 9.1 的"删除标记阻止写回"；派生数据（chunks / processing_tasks）物理删 + `ON DELETE CASCADE` 兜底
  - `processing_tasks.document_id` 唯一（落地 5.3"只产生一条处理记录"）；状态在 `documents.status` 与 `processing_tasks.stage` 各存一份，由 6.4 的单一迁移方法同事务写入
- 证据（可复现命令）：

  ```bash
  cd backend && .venv/Scripts/python.exe -c "
  import app.models
  from app.models import Base
  for t in Base.metadata.sorted_tables:
      print(t.name, [(c.name, str(c.type), c.nullable) for c in t.columns])
  "
  ```

  实测输出摘要：`users` 4 列 / `knowledge_bases` 5 列 / `documents` 13 列 / `chunks` 6 列 / `processing_tasks` 8 列；索引 `uq_kb_user_name ['user_id','name'] unique`、`idx_documents_kb ['kb_id']`、`ix_documents_user_id ['user_id']`；唯一约束 `uq_users_username`、`uq_chunks_document_chunk_index(document_id, chunk_index)`、`uq_processing_tasks_document_id(document_id)`
- 证据：`.venv/Scripts/python.exe -m pytest -q` → **21 passed, 0 skipped**（新增 `tests/test_models.py` 10 项；"无循环依赖"用子进程全新导入验证；末项连真实测试库按 metadata 建表并断言 5 表存在）

### 任务 2.2 Alembic 迁移与干净库验证

- 新增 `backend/alembic.ini`（**纯 ASCII**、不存连接串）、`alembic/env.py`（异步模板；URL 取自应用配置 `DATABASE_URL`，`import app.models` 保证 5 表全进 metadata，`compare_type=True`）、`alembic/script.py.mako`、`alembic/README`、`alembic/versions/0001_initial_schema.py`
- `backend/Dockerfile` 补 `COPY alembic.ini` / `COPY alembic`：容器内即可迁移，不必把库端口暴露到宿主

干净库 = compose 起的 pg 实例里新建的 `docmind_test`（本机无本地 PostgreSQL）：

```bash
docker exec docmind-pg psql -U docmind -d docmind -c "CREATE DATABASE docmind_test OWNER docmind"   # 初始 0 张表
cd backend
DATABASE_URL="postgresql+asyncpg://docmind:<口令>@127.0.0.1:5433/docmind_test" .venv/Scripts/alembic.exe upgrade head
```

| 检查项 | 命令 | 实测结果 |
|---|---|---|
| upgrade | `alembic upgrade head` / `alembic current` | `Running upgrade -> 0001, initial schema`；`0001 (head)` |
| 表 | `information_schema.tables` | 6 张 = 5 业务表 + `alembic_version` |
| `uq_kb_user_name` | `pg_indexes` | `knowledge_bases \| uq_kb_user_name \| unique=Y \| user_id, name` |
| `idx_documents_kb` | `pg_indexes` | `documents \| idx_documents_kb \| unique=N \| kb_id` |
| 外键级联 | `pg_constraint` | `chunks→documents ON DELETE CASCADE`、`processing_tasks→documents ON DELETE CASCADE`；`documents.kb_id→knowledge_bases` 无级联（RESTRICT，非空拒删的第二道闸门） |
| 列默认值 | `information_schema.columns` | `documents.status default 'uploaded'`、`chunk_count default 0`、`processing_tasks.stage default 'uploaded'`、两计数 `default 0`；`deleted_at` / `last_run_at` / `error_message` 可空 |
| 无 Enum CHECK 约束 | `information_schema.check_constraints`（须过滤 PG 呈现的 `*_not_null`） | **0**（状态列是 VARCHAR）；未过滤时为 33 = 32 个 NOT NULL + `alembic_version` 的 1 个 |
| downgrade | `alembic downgrade base` | 仅剩 `alembic_version` 且 **0 行**，`alembic current` 无输出，无残留索引 |
| 重复 upgrade | `alembic upgrade head` | 再次成功，6 张表 |
| 模型 ≡ 迁移 | `alembic check` | `No new upgrade operations detected.` |

- 开发库（compose 的 `docmind`）由**容器内**迁移，证明容器路径可用：`docker exec docmind-api alembic upgrade head` → `Running upgrade -> 0001`；`docmind` 库 6 张表、`alembic_version=0001`、两个 ADR 索引齐备

### 第 2 组任务状态

| 任务 | 状态 | 验证证据 |
|---|---|---|
| 2.1 五张表模型 | 完成 | metadata 快照 5 表逐列核对；`pytest -q` → **21 passed, 0 skipped**（含真实测试库建表用例） |
| 2.2 Alembic 迁移 | 完成 | `docmind_test` 干净库 upgrade→downgrade→upgrade 全通过；`uq_kb_user_name` / `idx_documents_kb` 实际存在；`alembic check` 无差异；`docker exec docmind-api alembic upgrade head` 亦成功 |

### 本轮修掉的环境问题（详见 findings D-026 / D-027）

- **D-026-1**：`alembic.ini` 含非 ASCII 时，alembic 以 GBK 读该文件 → `UnicodeDecodeError` 直接退出。规则：ini 纯 ASCII，中文说明写进 `env.py`。
- **D-026-2**：1.5 的 conftest 测试库口令（`docmind`）与 `.env`（`docmind_dev_pw`）不一致 → (a) 已修：从 `.env` 读 `POSTGRES_*` / `PG_HOST_PORT` 拼测试库连接串，支持 `TEST_DATABASE_URL` 覆盖，且改为直接赋值避免外部 `DATABASE_URL` 带偏。
- **D-027**：pytest-asyncio **1.4** 默认为每个用例建函数级事件循环，与 session 作用域 `db_engine` fixture 冲突 → 真实栈 `RuntimeError: Event loop is closed` → `AttributeError: 'NoneType' object has no attribute 'send'`，被 `check_database` 吞成"测试库不可达"→ **skip**。已修：`pyproject.toml` 固定 `asyncio_default_fixture_loop_scope` / `asyncio_default_test_loop_scope` 为 `session`，并加 `addopts = "-ra"` 强制汇总 skip；`check_database` / `check_redis` 增加失败日志（HTTP 响应仍只回类型名）。

### 留待后续组的衔接点

- **4.2 / 9.1**：知识库"文档数量"与"非空拒删"只统计 `deleted_at IS NULL`；删库前若只剩墓碑行需先物理清除，否则被 `fk_documents_kb_id_knowledge_bases` 拦住。
- **5.3**：`uq_processing_tasks_document_id` 已就位；分布式锁仍需应用层实现（唯一约束只是兜底）。
- **第 3 组（开工前必须停）**：JWT 签发库与密码哈希库属"新依赖"，先出 ADR 等批；`users.password_hash` 已按 VARCHAR(255) 预留。
- **`docmind_test` 使用约定**：`pytest` 的 `db_schema` fixture 会按 metadata 建表、跑完 drop 表（但保留 `alembic_version` 行）。因此跑完测试若要用 alembic 验库，先复位：
  `docker exec docmind-pg psql -U docmind -d docmind_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"`
  再 `DATABASE_URL=…/docmind_test alembic upgrade head`。
