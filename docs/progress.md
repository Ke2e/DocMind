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

## 2026-09-12（第 3 组开工前的停机点：ADR-0002 选型）

> 本次**未实施任何任务**，只产出停机点要求的 ADR。`tasks.md` 仍为 8/35，无勾选变化。

### 开工前基线复核（真实命令，非印象）

| 检查项 | 命令 | 实测结果 |
|---|---|---|
| 提交与工作区 | `git log --oneline -3` / `git status --short` | HEAD = **`d9a1cb2`**（第 3 次交接文档），工作区**干净**（无输出） |
| 任务进度 | `openspec list` | `add-doc-ingest-pipeline  **8/35 tasks**` |
| 容器 | `docker compose ps` | api / beat / nginx / pg / redis / worker **6/6 running healthy** |
| **对外链路**（healthy 不算证据） | venv 内 httpx `GET http://127.0.0.1:8080/health/{live,ready}` | `/health/live` → **200** `{"status":"ok"}`；`/health/ready` → **200**，`{"checks":{"database":null,"redis":null}}` |
| 依赖缺口 | `pip list \| grep -iE "jwt\|jose\|passlib\|argon\|bcrypt\|crypt"` | **0 命中** → 3.1/3.2 所需依赖确实一个都没有 |
| 依赖声明方式 | `find backend -name "*.txt" -not -path "*/.venv/*"` / 找 lockfile | **均无** → 依赖只在 `pyproject.toml`，镜像走 `pip install .`，故新依赖必须进 `dependencies` 才进镜像 |

### 产出：`docs/adr/0002-auth-libraries.md`（Proposed，待批）

- 决策建议：**PyJWT**（`pyjwt>=2.9`）做凭证签发与校验 + **argon2-cffi**（`argon2-cffi>=23.1`）做密码哈希（argon2id，直接用，**不经 passlib**）
- 同时定下 4 条配套约定（payload 只放 `sub/iat/exp`、`Authorization: Bearer`、校验失败一律 401 且不区分原因、**用户名不存在时也要跑一次假哈希防时序侧信道**），避免 3.x 实现时各写各的
- 被否方案 7 个：python-jose / 自研 HS256 / passlib / 直接 bcrypt / stdlib scrypt·pbkdf2 / authlib / RS256
- 合规声明（AGENTS.md §1 强制）：保护清单不含密码学（原则 I 不冲突，且密码学属"不该自研"）；技术栈清单未列鉴权库（原则 II 下本次属技术栈新增，故须经本 ADR）
- **明确不改 DDL**：`users.password_hash VARCHAR(255)` 本就是按 argon2id 输出预留（见 `app/models/user.py` 注释），选 argon2id 与任务 2.1 的模型设计一致 → 不触发第二次 DDL 停机点

### 选型事实全部查证（不凭记忆）

| 库 | 最新版 / 发布日 | 结论 |
|---|---|---|
| PyJWT | 2.14.0 / 2026-09-11 | 维护活跃（前一天刚发版） |
| argon2-cffi | 25.1.0 / 2025-06-03 | 维护活跃 |
| passlib | **1.7.4 / 2020-10-08** | **停更 5 年**；且与 `bcrypt>=4.1` 不兼容（`bcrypt.__about__` 被移除），Gentoo#925289 / Debian#1082011 / pyca/bcrypt#684 均有实证 → **否决** |
| python-jose | 3.5.0 / 2025-05-28 | CVE-2024-33663 / 33664 **已于 3.4.0 修复**，现行版不受影响（表述须准确，不能当成"现网仍有洞"） |

**可安装性实测**（本机 cp312 / win_amd64）：`pip install --dry-run` 完整闭包 →
`PyJWT-2.14.0 argon2-cffi-25.1.0 argon2-cffi-bindings-26.1.0 cffi-2.1.1 pycparser-3.0`，
且 `pip download` 拿到的全是预编译 wheel（`argon2_cffi_bindings-26.1.0-cp310-abi3-win_amd64.whl`、`cffi-2.1.1-cp312-cp312-win_amd64.whl`）→ **Windows 侧无需源码编译**。

> 未验证项：**镜像侧（linux manylinux）未实测**，已写进 ADR 的"批准后动作"第 3 步——`docker compose up -d --build` 后必须进容器 `import jwt, argon2` 复核。

### 停机点状态

- **停在停机点 3（架构级决策）**：等开发者批 ADR-0002。批准前**不安装依赖、不写 3.x 代码**。
- 未做跳步项 `6.1 先写分块算法测试`（零新依赖但属跳步，需开发者点头），本次**未动**。
- 本次改动仅 3 个文档文件：新增 `docs/adr/0002-auth-libraries.md`，追加 `docs/progress.md`（本节）、`docs/findings.md`（D-028）。**未提交**。

## 2026-09-12（第 3 组：账号体系）

### 停机点 3 通过：ADR-0002 获批

- 开发者批复「全部批准」→ ADR-0002 状态 **Proposed → Approved**；批准前未装任何依赖、未写 3.x 代码
- 依赖落地位置：**只有** `backend/pyproject.toml` 的 `dependencies`（仓库无 requirements.txt / lockfile，镜像走 `pip install .`）
  - 追加 `pyjwt>=2.9`、`argon2-cffi>=23.1`
- 版本与实测：pyjwt **2.14.0** / argon2-cffi **25.1.0**；argon2id 摘要 **97 字符**、单次哈希 **56ms** / 校验 **55ms**
  （默认参数 `time_cost=3` / `memory_cost=64MiB` / `parallelism=4`）→ 97 字符落进 `VARCHAR(255)` 余量充足，**不需要改 DDL**

### 交付物

新增（后端）：

- `app/core/security.py` —— argon2id 哈希 + 凭证签发/校验（纯函数，不碰 DB）
- `app/schemas/auth.py` —— 用户名归一化 + 密码强度校验 + 请求/响应模型
- `app/services/auth.py` —— 注册 / 校验凭证（哈希与校验走 `asyncio.to_thread`）
- `app/api/routes/auth.py` —— `POST /api/auth/register`、`POST /api/auth/login`、`GET /api/auth/me`

新增（测试与验收）：

- `tests/test_security.py` —— 算法层单测（哈希、凭证签发/校验的否定用例）
- `tests/test_auth_api.py` —— 接口层验收（3.1 / 3.2 / 3.3 三组）
- `tools/verify_auth_e2e.py` —— **经 nginx 的真实 HTTP** 端到端验收脚本（10.1 会并入统一入口）

修改：

- `app/api/deps.py` —— 新增 `get_db_session`（每请求一个事务边界）与 `get_current_user`（鉴权唯一入口）
- `app/core/errors.py` —— 新增 `UnauthorizedError`
- `app/main.py` —— 挂载 auth 路由
- `tests/conftest.py` —— 双账号 fixture（`Account` / `account_factory` / `two_accounts`），补 1.5 遗留项

### 第 3 组任务状态

| 任务 | 状态 | 验证证据 |
|---|---|---|
| 3.1 注册接口 | 完成 | 成功 → 201 且响应体只有 `{id, username}`；重复 → 409 `conflict` 且库内用户数仍为 1；5 组弱密码参数化 → 422 且 `detail` 点名具体不满足项、同时断言不产生账号；库内落 `$argon2id$` 摘要，口令原文不入库 |
| 3.2 登录与凭证签发 | 完成 | 登录换取 token 并立即可访问受保护接口；`expires_in=86400`；payload 断言只有 `sub/iat/exp`；**密码错与用户不存在响应体逐字节相同**且两条路径耗时都 >10ms；过期 / 他人密钥签名 / `alg=none` / `sub` 非数字全部被拒 |
| 3.3 鉴权依赖 | 完成 | 无凭证 / 格式非法 / 伪造 / 过期 / 账号已删 5 组一律 401 且不区分原因；**归属判据**：带 A 的凭证 + 请求体写 B 的 `user_id` → 探针返回 `authenticated_user_id = A.id`，证明请求体身份被忽略 |
| （1.5 遗留）双账号 fixture | 完成 | `tests/conftest.py` 走真实注册 + 登录接口构造 `Account`，未直接插库 |

### 证据（可复现命令与输出）

```bash
# 1) 单测（ASGI 直连）
cd backend && .venv/Scripts/python.exe -m pytest -q
# → 54 passed in 13.31s
#   注意：**0 skipped**（本组开工前为 21 passed）
#   ⚠️ 断言"0 skipped"不能只看"passed"——`-ra` 的汇总行里没有 skip 才算数

# 2) 端到端（经 nginx 打真实 HTTP；本机无 curl）
cd backend && .venv/Scripts/python.exe ../tools/verify_auth_e2e.py
# → 合计 11 项，FAIL 0 项，EXIT=0

# 3) 镜像侧两个新依赖（ADR-0002 的遗留验证项，本次关闭）
docker exec docmind-api python -c "import importlib.metadata as md; print(md.version('pyjwt'), md.version('argon2-cffi'))"
# → 2.14.0 25.1.0   （容器内 sys.platform = linux，argon2id 产出 $argon2id$v=19$m=65536,t=3,p=4$…）

# 4) 容器
docker compose ps --format 'table {{.Name}}\t{{.State}}\t{{.Health}}'
# → api / beat / nginx / pg / redis / worker 6/6 running healthy
```

e2e 关键响应原文：

| 检查 | 实测响应 |
|---|---|
| 注册成功 | `201 {"id":4,"username":"e2e_3x_…"}` |
| 用户名重复 | `409 {"code":"conflict","message":"该用户名已被占用，请换一个"}` |
| 弱密码 | `422 {"code":"validation_error",…,"reason":"Value error, 密码不满足要求：包含数字"}` |
| 登录失败（两种原因） | `401 {"code":"unauthorized","message":"用户名或密码不正确"}` ×2，逐字节相同 |
| 无凭证 | `401 {"code":"unauthorized","message":"请先登录"}` |
| 伪造凭证 | `401 {"code":"unauthorized","message":"登录状态已失效，请重新登录"}` |

### 本轮踩到并修掉的问题（详见 findings）

- **D-029**：前台 `pip install` 被 SIGTERM 中断 → venv 里 **9 个包**变成空壳（`ImportError: … (unknown location)`，`__file__` 为 None 即命名空间包）。
  修复路径：重命名挪开损坏 venv → 用系统解释器 3.12.3 重建 → 装依赖 → 全量探测 **67/67 可导入**。新增机器级规则：`pip install` / `docker build` / 大套件 pytest 一律后台跑。
- **D-030**：`OAuth2PasswordBearer` 返回的是**原始 token 字符串**，不是 `HTTPAuthorizationCredentials`（那是 `HTTPBearer` 的返回类型）→ 7 个用例同时变红（本该 401 的请求变成 500）。测试一次就抓住。
- **D-031**：容器刚重建完就发写请求，那一轮的注册行没落库（id=1 缺失，之后的 id=2/3/4 都正常）。
  教训：**写操作的端到端验收要等容器稳定后再跑**；**"成功"以查库为准，不能只看接口回了 201**（当时 11/11 全绿，完全看不出问题）。

### 数据与环境收尾（已复核）

- 开发库 `docmind`：验收用 `e2e_*` / `probe_*` 账号已 `DELETE` 清理，`SELECT count(*) FROM users` → **0**
- 测试库 `docmind_test`：public schema 仅剩 `alembic_version`（pytest 的 `db_schema` fixture 约定，非残留）
- 损坏的 `backend/.venv.damaged-20260912` 已删除；新 `backend/.venv` 全量探测 67/67 可导入
- 本次改动**未提交**

### 两项"规格未规定"已由开发者定案（2026-09-12，本人作答）

| 项 | 结论 | 落地 |
|---|---|---|
| 用户名大小写 | **区分大小写**（保持现状，零行为改动） | 写进 `user-auth` 规格 Requirement + 新增「用户名区分大小写」场景；测试 `test_register_is_case_sensitive_on_username` |
| 密码长度上限 | **上限 128 字符** | 配置 `PASSWORD_MAX_LENGTH=128`（`.env.example` 同步）；`schemas/auth.py` 校验并点名；超限用例 + **恰好 128 必须通过**的边界用例 |

改规格走了 `openspec-update-change` 流程，触及 2 处规划件：`specs/user-auth/spec.md`（Requirement 1 处 + 场景 1 处）
与 `tasks.md`（业务参数清单 1 处 + 强度规则 1 处）；proposal / design 无涉及，已 grep 确认。
改完 `openspec validate add-doc-ingest-pipeline --strict` → **valid**。

> 说明：上限进 `Settings`、而 argon2 的 `time_cost`/`memory_cost` 不进（ADR-0002 D2）——前者是输入护栏，后者是抗爆破旋钮，性质不同。

### 本组代码审查（第 3 组提交前，走 AGENTS.md §4 门禁）

两轴并行子代理审查（基线 `d9a1cb2` → 工作区）：

| 轴 | 结论 | 处置 |
|---|---|---|
| Standards（对 `AGENTS.md` / constitution / 两个 ADR / findings） | **无硬违规**；4 条判断题 | 1 条已修：`tools/verify_auth_e2e.py` 硬编码端口 `8080` 与 `86400` → 改为从 `.env` 读 `NGINX_HOST_PORT` / `TOKEN_EXPIRE_MINUTES`；2 条论证后接受不改（`username max_length=64` 对齐 DDL、`_DUMMY_PASSWORD` 非密钥） |
| Spec（对 `specs/user-auth/spec.md` + tasks 3.x + design D10 + ADR-0002 D4） | 整体忠实 | 3 项"规格未覆盖"记录在案、**未擅自改规格**，见下 |

**Spec 轴记录的 3 项规格未覆盖（等开发者定，未擅自改）**：

1. `3.3` 的越权**写**操作要等 4.1 / 5.2 有接口后端到端验（tasks.md 已注明 defer，非缺陷）
2. 用户名**两端去空白归一化**与**长度上限 64 / 非空** —— 规格未写，是实现在输入层加的规范化
3. `GET /api/auth/me` —— 规格未显式要求，作为 3.3 的受保护接口样本存在

**按审查意见加强的测试**：`test_login_does_the_same_hash_work_for_an_unknown_user` —— monkeypatch 计数证明
"用户不存在时也恰好跑一次校验、入参为 `None`"，比原先只断言"两条路径耗时都 >10ms"更硬（在断言机制而非旁证）。
测试总数 **54 → 58**（均为 0 skipped）。

### 审查"规格未覆盖"项收口（2026-09-13）

开发者授权"按推荐来"，故定案如下（详见 `docs/findings.md` D-034）：

| 审查发现 | 处置 | 落地 |
|---|---|---|
| 用户名"非空 / 长度 ≤64 / 忽略两端空白" | **回写规格** | 「账号注册」Requirement 补 3 条约束；新增「用户名不合法」「用户名两端空白被忽略」两个场景 |
| `GET /api/auth/me` | **回写规格** | 新增「当前账号自省」Requirement + 2 个场景（成功返回身份 / 凭证不可用一律拒绝） |
| 3.3 越权**写**操作要等 4.1 / 5.2 | **保持现状** | defer 已写在 tasks.md，4.1 与 5.2 的验收方式本身含跨账号用例，再补说明是冗余 |

- 改完复核：`openspec validate add-doc-ingest-pipeline --strict` → **valid**
- 选择"回写规格"而非"撤掉实现"的理由：这三条都是**已实现且合理**的行为；撤掉会更糟（用户以为两端空白无意义，实际却注册出两个账号）

**同批修掉 D-033（镜像构建缺缓存）**：

- `backend/Dockerfile` 去掉 `PIP_NO_CACHE_DIR=1`，给 pip 的 `RUN` 加 `--mount=type=cache,target=/root/.cache/pip`
- **实测（可复现）**：

  | 场景 | 耗时 | 日志证据 |
  |---|---|---|
  | 修复前：改 `app/` 后重建 | **41 分 37 秒** | `Downloading` 逐条走网络（慢到 14 kB/s） |
  | 修复后首次构建（缓存为空） | 9 分 16 秒 | `Downloading` 115 行 / `Using cached` **0** 行 → 仍全量下载，提速只是网络变好 |
  | 修复后再改一行重建 | **1 分 27 秒** | `Downloading` **0** 行 / `Using cached` **115** 行 → 依赖全部命中缓存 |

  判据用 `Downloading`/`Using cached` 计数而非耗时——耗时会被网络带偏（中间那次 9 分钟就是差点被误记成"缓存生效"的例子）。
- 验证方式（可复现）：往 `backend/app/` 任一文件加一行注释 → `docker compose build` → 看日志计数；本次实验的探针已复原（`git status` 干净）

### 交接材料刷新（第 4 次交接，2026-09-12）

- `docs/HANDOFF.md`：整体重写到第 3 组完工状态 —— 当前状态（含"未提交"改动清单）、下一步第 4 组与 D-024 衔接点、
  环境速查表新增 4 行（重命令被 SIGTERM 掐断 / pip 中断打残 venv / PowerShell 不回显 / 换容器窗口写请求不可信）、
  决策表新增 ADR-0002 与凭证契约、工件地图补本组新增文件、待办新增"无 lockfile"与"两个未规定项"
- `docs/新会话提示词.md`：主提示词同步到 11/35（第 3 组完工、下一站第 4 组），环境段与工程纪律段补入第 3 组的坑；
  变体 C 的进度数字由 8/35 更新为 11/35
- 核验方式：对两份文件 grep 过期残留词（`第 3 次交接` / `8/35` / `21 passed, 0 skipped` / `卡在停机点上` /
  `先出 ADR-0002` / `1.3 容器健康核验中`）→ 均为 0 命中（HANDOFF 里 1 处"第 3 次交接"是提交信息的历史引用）；
  再 grep 新事实锚点（`11/35` / `54 passed` / `11/11 PASS` / `未提交` / `ADR-0002` / `D-031`）→ 全部命中

---

## 2026-09-13（第 4 组：知识库）

### 开工前基线复核（真实命令，非印象）

```bash
docker compose ps --format 'table {{.Name}}\t{{.State}}\t{{.Health}}'
# → api / beat / nginx / pg / redis / worker 6/6 running healthy

cd backend && .venv/Scripts/python.exe -m pytest -q
# → 58 passed in 12.09s（汇总行无 skipped）

git log --oneline -1 && git status --short
# → b464f22；工作区干净
```

### 交付物

| 类别 | 文件 |
|---|---|
| 新增（4） | `backend/app/schemas/knowledge_base.py`、`app/services/knowledge_base.py`、`app/api/routes/knowledge_bases.py`、`backend/tests/test_knowledge_base_api.py` |
| 新增（验收） | `tools/verify_knowledge_base_e2e.py` —— 经 nginx 真请求 + **查库核实**（10.1 会并入统一入口） |
| 修改（1） | `backend/app/main.py`（挂载 knowledge_bases 路由） |

**无新增依赖、无 DDL 变更、无 collection 变更** → 未触及停机点（本组开工前开发者已确认「不需要新依赖，不涉及停机点」）。

### 接口清单

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/knowledge-bases` | 列出自己的库，每条带 `document_count`（只算非墓碑文档） |
| `POST` | `/api/knowledge-bases` | 创建；名称同账号内唯一，201 |
| `PATCH` | `/api/knowledge-bases/{kb_id}` | 重命名（可一并改简介） |
| `DELETE` | `/api/knowledge-bases/{kb_id}` | 非空拒删，204 / 409 |

### 第 4 组任务状态

| 任务 | 状态 | 验证证据 |
|---|---|---|
| 4.1 创建 / 列表 / 重命名 | 完成 | 重名 409、空名与超长（129 字）422 且点名原因、**恰好 128 字通过**、`"  "+128 字` 通过（锁「先 strip 再判长」的顺序）；列表 `document_count` **只算 `deleted_at IS NULL`**（2 在册 + 1 墓碑 → 回 2）；双账号交叉列表互不可见；**重命名他人库 404 且查库名字未变**；请求体塞 `user_id` 建库 → 查库确认归属仍是自己（3.3 越权写 defer 收口） |
| 4.2 删除（非空拒删） | 完成 | 空库 204 且从列表与库中消失（查库）；非空库 409 且 `message` + `detail.document_count` 给出未清空数量，库与文档都完好（查库复核）；**只剩墓碑行的库可删**（D-024 衔接点）；绕过接口直接删库行被 RESTRICT 外键拦下（`IntegrityError`） |

### 证据（可复现命令与输出）

```bash
# 1) 单测（ASGI 直连）
cd backend && .venv/Scripts/python.exe -m pytest -q
# → 93 passed in 28.98s
#   基线 58 → 93（本组新增 35 个用例）；⚠️ 汇总行无 skipped，才是真的 0 skipped

# 2) 端到端（经 nginx 打真实 HTTP；本机无 curl）
cd backend && .venv/Scripts/python.exe ../tools/verify_knowledge_base_e2e.py
# → 合计 26 项，FAIL 0 项，EXIT=0
#   跑了**两轮**：审查前代码 26/26，审查修正后重建镜像再跑仍是 26/26（第二轮输出见下）

# 3) 镜像重建（findings D-034 的缓存修复，本轮两次实测）
docker compose up -d --build
# → 1 分 26 秒 ×2（改 app/ 后重建；判据见 D-034 —— 缓存命中的话日志里 Downloading 为 0 行）
docker exec docmind-api python -c "import app.main as m; print(len(m.app.routes))"
# → 7（4 条 Framework 默认 + 3 个 _IncludedRouter，即 health / auth / knowledge_bases 三个路由器）

# 4) 开发库状态（写操作以查库为准）
docker exec docmind-pg psql -U docmind -d docmind -tAc \
  "SELECT 'users='||count(*) FROM users UNION ALL SELECT 'kbs='||count(*) FROM knowledge_bases UNION ALL SELECT 'docs='||count(*) FROM documents;"
# → users=0 / kbs=0 / docs=0（e2e 脚本自清，且已由脚本内「收尾：本轮测试数据已清空（查库）」断言）

# 5) 迁移状态（本组无 DDL 变更，确认无漂移）
docker exec docmind-api alembic current   # → 0001 (head)
docker exec docmind-api alembic check     # → No new upgrade operations detected.
```

第二轮 e2e 的输出（修正后、重建镜像后复跑，节选）：

```
PASS  准备：双账号注册并登录   [a.id=9 b.id=10]
PASS  4.1 请求体里的 user_id 被忽略（查库归属）   [201 owner=9（写在 body 里的是 bob=10）]
PASS  4.1 列表文档数量=2（墓碑行不计入）   [document_count=2，库里实际 3 行]
PASS  4.2 非空拒删 409 且给出未清空数量   [409 {"code":"conflict","message":"该知识库下还有 2 份文档，请先清空后再删除","detail":{"document_count":2}}]
PASS  4.2 只剩墓碑行的库可删 204（D-024 衔接点）
PASS  收尾：本轮测试数据已清空（查库）   [0 / 0]
合计 26 项，FAIL 0 项
```

e2e 关键响应原文（节选，全部 26 项见脚本输出）：

| 检查 | 实测响应 |
|---|---|
| 创建成功 | `201 {"id":1,"name":"e2e 库 1789293206","document_count":0,…}` |
| 同账号重名 | `409 {"code":"conflict","message":"该名称的知识库已存在，请换一个"}` |
| 空名 | `422 {"code":"validation_error",…,"reason":"Value error, 知识库名称不能为空"}` |
| 超长名（129 字） | `422 … "reason":"Value error, 知识库名称长度不超过 128 个字符"` |
| 重命名他人库 | `404`（查库仍是原名字） |
| 非空拒删 | `409 {"code":"conflict","message":"该知识库下还有 2 份文档，请先清空后再删除","detail":{"document_count":2}}` |
| 空库删除 | `204`（无响应体） |

### 本轮的两处实测（一条证伪、一条证实，详见 findings D-036）

- **证伪**：初稿在 `create_knowledge_base` 路由里写了 `await session.refresh(kb)`，注释断言"不 refresh 会抛 MissingGreenlet"。
  把那行注释掉跑 `-k "create or list_includes"` → **16 passed** —— SQLAlchemy 2.0 在 asyncpg 上会用
  `INSERT ... RETURNING` 带回 `server_default` 生成的 `id` / `created_at`，refresh 纯属多余。已删该行并把注释改成实测结论。
  （教训：注释里的因果也要有证据，否则会被下一个人当事实继承。）
- **证实**：`tools/verify_knowledge_base_e2e.py` 里读容器 psql 输出必须显式 `encoding="utf-8"`——
  本机 locale 是 GBK，而容器 psql 吐 UTF-8，默认编码解码会把库名读成乱码，而该脚本的"查库核对"正是拿读回的字符串比对，
  乱码会让核对变成**假失败**（且看起来像"数据没落库"，极易把人带偏）。

### 本组三个判断题（记入 findings D-035，均已定，勿再反复）

| 判断 | 结论 |
|---|---|
| 越权访问他人知识库的状态码 | **404**（403 会把"他人资源是否存在"变成可探测信息）；落地方式是把 `id` 与 `user_id` 放同一条 WHERE |
| 重命名未带 `description` | **保留原值**（PATCH 语义）；service 用 `UNSET` 哨兵 + 路由用 `model_fields_set` 区分"没传"与"传 null" |
| 名称大小写 / 长度上限来源 | 不归一小写（沿用户名口径）；上限取模型常量 `KB_NAME_MAX_LENGTH`（= DDL），不另设配置项 |

### 提交前的两轴审查（走 AGENTS.md §4 门禁，详见 findings D-038）

两轴只读子代理并行（基线 `b464f22` → 工作区）：Standards 轴对 `AGENTS.md` / constitution / 两个 ADR / findings；
Spec 轴对 `knowledge-base` 规格 + tasks 4.x。

| 轴 | 结论 | 处置 |
|---|---|---|
| Standards | **1 条硬违规** + 6 条判断题 | 硬违规已修：`count_live_documents` 与墓碑清除两条**文档域**语句漏了 `user_id`，同时注释把红线出处写成 §6（实为 **§5 禁改清单**）；已补过滤 + 改正出处 |
| Spec | 规格 7 个 Scenario **全部"实现 + 测试"双覆盖**；发现 4 个 PATCH 写用例**只看响应体没查库** | 已补查库断言（含"不传 description 应保留原值"这条高危路径）；另有 2 项建议回写规格、4 项建议记录在案 —— **未擅自改规格**，列入待开发者表态 |

**审查引出的实现缺陷（比原报告的问题更严重，已修）**：

原报告只把"计数与删除之间的并发窗口"列为判断题，担心抛 500。顺着追下去发现当时的墓碑清除写的是
**"删除该库全部文档"**（`deleted_at` 不带条件）—— 它把正确性押在"计数之后没有新文档落进来"这个假设上。
一旦窗口内真有一份**在册**文档落进来（例如用户刚上传完就删库），这句会**连那份刚上传的文档一起物理删掉**、
再删库成功，接口回 **204 成功** —— 静默的数据丢失，比报错严重得多。

修法三步：墓碑清除加 `deleted_at IS NOT NULL`（只删墓碑行）→ 并发落进来的在册文档被 RESTRICT 外键拦下 →
`except IntegrityError → ConflictError` 翻译成 **409**（原来会冒 500）。新增
`test_delete_race_with_a_concurrent_insert_is_refused`：monkeypatch 把 `count_live_documents` 钉成 0
以**稳定复现**该窗口，断言"409 + 库与那份文档都还在"。

**其余判断题处置**：删掉 `normalize_kb_name` 里的死代码守卫（J1）、删掉 `KnowledgeBasePublic` 上自相矛盾的
`from_attributes`（J2）、e2e 脚本改为 `import KB_NAME_MAX_LENGTH` 不再抄 128/129（J3）、
`stub_document` 改为只接受整数索引使字符串不进 SQL（J6）、rename 侧补"点名名称限制"断言（J5）。

**规格未覆盖项（等开发者定，未改规格）**：`description` 字段与 PATCH 语义、列表 `document_count` 的口径
（= `deleted_at IS NULL`，来自 D-024）**建议回写规格**；列表排序、重命名幂等、名称 strip 与大小写、
响应额外字段**建议记录在案**。

### 数据与环境收尾（已复核）

- 开发库 `docmind`：`users=0` / `knowledge_bases=0` / `documents=0` / `chunks=0` / `processing_tasks=0`
- 测试库 `docmind_test`：public schema 仅剩 `alembic_version`（pytest 的 `db_schema` fixture 约定，非残留）
- `openspec list` → **13/35 tasks**
- 容器 6/6 healthy；本轮改动**已提交**：交付 `7fdecd1`（11 文件，+1651/−46）
