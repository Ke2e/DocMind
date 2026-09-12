# DocMind 开发交接文档

**交接时间**：2026-09-12（第 3 次交接）
**交接范围**：W5 第 1 组运行环境（1.1–1.6）+ 第 2 组数据模型与迁移（2.1–2.2）已完成；下一站是第 3 组，但**先到停机点**
**给下一个会话**：读完本文 + `AGENTS.md` 即可接手，不需要回溯聊天记录

---

## 一、当前状态（一句话）

第 2 组已完成并提交 **`98735be`**（工作区干净）；`openspec list` → **8/35 tasks**、`validate --strict` 通过；
开发库 `docmind` 与测试库 `docmind_test` 都已在 Alembic **`0001`**（5 张业务表 + `alembic_version`）；
6/6 容器 healthy（pg 5433 / redis 6380 / nginx 8080），经 nginx 打真实请求 `/health/ready` → 200；
`pytest -q` → **21 passed, 0 skipped**。
**下一项第 3 组（账号体系）整个卡在停机点上**：`3.1`/`3.2` 需要的 JWT 签发库与密码哈希库属"新依赖"，必须先出 ADR 等开发者批准，不得自行选型。

**最近一次提交拓扑**

| 提交 | 内容 |
| --- | --- |
| `98735be` | 第 2 组数据模型与迁移落地（2.1–2.2）+ 修掉 3 个环境缺陷 |
| `3210f38` | 刷新交接文档与开工提示词到第 1 组完工后的状态 |
| `b531d27` | 第 1 组运行环境落地（1.2–1.6） |
| `ad2e410` | 新增新会话开工提示词 |
| `bd6e9f6` | 配置对齐实际网关并补齐交接文档与验收语料 |
| `d34b36b` | 初始化仓库并落地 W5 规格基线与 OpenSpec 提案 |

---

## 二、下一步从哪开始

1. **先出 ADR-0002（JWT 签发库 + 密码哈希库选型），停下等批**。写法照 `docs/adr/0001-knowledge-base-entity.md`
   （背景 / 决策 / 被否方案 / 批准后要做的动作）。已经就位的约束，选型时直接用：
   - `users.password_hash` 是 `VARCHAR(255)`（按 argon2id 输出留的余量）
   - 配置项已存在（任务 1.4）：`JWT_ALGORITHM`、`TOKEN_EXPIRE_MINUTES`、`PASSWORD_MIN_LENGTH`
   - 规格要求：密码**不可还原**存储；用户名唯一；登录失败响应**不区分**"用户不存在"与"密码错误"
2. **ADR 批准后**按 tasks.md 顺序：3.x 账号体系（含 1.5 遗留的"双账号 fixture"）→ 4.x 知识库 →
   5.x 上传受理 → 6.x 后台管线 → 7.x 状态与进度 → 8.x 失败重试与中断补偿 → 9.x 删除清理 → 10.x 验收留档
3. **想在等批期间不空转**：`6.1 先写分块算法测试`（保护清单要求的 TDD 前置）零新依赖、不碰任何模型服务，
   可以先写测试、不写实现——但这是**跳步**，需开发者明确点头后再做

---

## 三、本机环境速查（踩过的坑，务必先看）

| 坑 | 现象 | 对策 |
| --- | --- | --- |
| **Bash 工具 PATH 会被清空** | `ls`/`grep`/`dirname` 等 coreutils 报 `command not found`，npm shim 解析失败（曾误判 openspec 未安装） | 每条命令开头显式设置 PATH（见下） |
| `git.exe` 不在 PortableGit/bin | `git: command not found` | 需把 `.../PortableGit/versions/1.2.0/cmd` 加进 PATH |
| 沙箱只允许写工作区内 | 往 `C:\Users\ASUS\.workbuddy\...` 建 venv 静默失败（exit 0 但无目录） | 依赖装进项目内 `.venv/`（已在 .gitignore） |
| PowerShell 工具不回显 stdout | 命令 exit 0 却看不到输出 | 改用 Bash；必须用 PS 时改看退出码 + 之后用 Glob/Read 核验 |
| **`docker.exe` 不在 PATH** | `docker: command not found` | Docker Desktop 装在 **`D:\Docker\App`**（非默认路径），把 `/d/Docker/App/resources/bin` 前置进 PATH |
| **本机没有 `curl`** | HTTP 探针全部失败 | 用 `backend/.venv/Scripts/python.exe` + httpx 打真实请求 |
| **裸 `python` 不在 PATH** | `python: command not found` | 一律写全路径（`backend/.venv/Scripts/python.exe`） |
| **本机无本地 PostgreSQL / psql** | 连不上库 | 数据库只能走 compose 起的 pg（宿主 `127.0.0.1:5433`）；**查库用 `docker exec docmind-pg psql -U docmind -d <db> -c "..."`**（容器内有 psql） |
| **宿主端口已被别的项目占用** | `up` 后连错服务 | OneHub 占 8000/5432/6379；既有 Milvus（project `lk_ai`）占 9000-9001/9091/19530 → DocMind 用独立 project name `docmind` + pg 5433 / redis 6380 / nginx 8080 |
| **`docker compose ps` 报 healthy 不等于链路可用** | 六容器全绿但经 nginx 是 502 | 凡"链路通"的结论**必须打真实请求**验证 |
| **nginx 只在启动时解析一次上游主机名** | api 容器重建换 IP 后 nginx 持续 502 | 已修：`docker/nginx.conf` 用 `resolver 127.0.0.11 valid=10s` + 变量化 `proxy_pass` |
| **同批并行编辑同一文件会丢改动** | 字段没落盘，worker/beat 反复重启 | 同一文件的编辑串行执行，改完复核内容 |
| **宿主端口映射被 Compose 覆盖**（自定义 host 名无法从宿主直连） | 宿主跑 alembic / pytest 连不上 `pg` | `.env` 里 host 用 `127.0.0.1:5433`（宿主视角），容器内由 compose 覆盖为 `pg:5432` |
| **`alembic.ini` 必须纯 ASCII**（第 2 组新增） | 写 UTF-8 中文注释 → alembic 用 locale 编码（本机 GBK）读 ini，`UnicodeDecodeError` 直接退出 | ini 保持 ASCII；中文说明写进 `alembic/env.py`（.py 恒按 UTF-8 读） |
| **测试库连接串别抄口令**（第 2 组新增） | 1.5 的 conftest 硬编码口令与 `.env` 不一致 → 所有库用例**静默 skip**（输出仍是"通过"） | 已改为从 `.env` 读 `POSTGRES_*` / `PG_HOST_PORT` 拼 `docmind_test`，`TEST_DATABASE_URL` 可覆盖。**skip ≠ 通过** |
| **pytest-asyncio 1.4 的事件循环**（第 2 组新增） | session 作用域异步 fixture（`db_engine`）跨循环用连接 → `Event loop is closed` / `AttributeError: 'NoneType' object has no attribute 'send'` | `pyproject.toml` 已固定 `asyncio_default_fixture_loop_scope` / `asyncio_default_test_loop_scope` = `session`，并加 `addopts = "-ra"` |
| **跑完 pytest 用 alembic 验库前要先复位**（第 2 组新增） | `db_schema` fixture 按 metadata 建/销表，但保留 `alembic_version` 行 → `upgrade head` 变成空操作 | `docker exec docmind-pg psql -U docmind -d docmind_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"` 再 `alembic upgrade head` |
| **探测函数别把异常压成类型名**（第 2 组新增） | `check_database` 只回 `AttributeError`，掩盖了真实的 `Event loop is closed` | 已改为同时写日志（HTTP 响应仍只回类型名） |

**统一 PATH 前缀（建议每条 Bash 命令都用）：**

```bash
export PATH="/d/Docker/App/resources/bin:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/cmd:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/d/nvm/nodejs:/usr/bin:/bin"
```

**已就绪的工具**

- `openspec` v1.11.0（`D:\nvm\nodejs` → nvm v24.9.0）
- `specify`（spec-kit）v1.0.1 —— 仅历史用途，不再驱动开发
- git 2.55.0，全局身份 `Asize <3238075590@qq.com>`
- Docker Desktop（CLI 29.7.2 / daemon linux / compose v5.3.1）—— 已常驻 `docmind` 栈
- **Alembic 已接入**（第 2 组）：宿主用 `backend/.venv/Scripts/alembic.exe`，容器内用 `docker exec docmind-api alembic upgrade head`
  （Dockerfile 已 `COPY alembic.ini` / `COPY alembic`）；常用命令与两个坑见 `backend/alembic/README`
- **测试基线**：`cd backend && .venv/Scripts/python.exe -m pytest -q` → **21 passed, 0 skipped**
- **两个虚拟环境，勿混用**：
  - 仓库根 `.venv/`（Python 3.13.14）+ reportlab / python-docx / pillow / pypdf —— **只用于生成验收语料**（`tools/gen_acceptance_corpus.py`）
  - `backend/.venv/`（Python 3.12.3，系统解释器 `D:\IDE\Python\Python312`）—— 后端运行时与测试，已装齐 FastAPI / SQLAlchemy / asyncpg / Alembic / Celery / redis / pypdf / python-docx / tiktoken / pytest / pytest-asyncio / httpx

---

## 四、已冻结的决策（不要再重新讨论）

| 项 | 结论 | 权威出处 |
| --- | --- | --- |
| 规格流程 | **OpenSpec 单主线**（`changes/` → apply → archive）；spec-kit 仅作 W5 启动文档，`/speckit.*` 已弃用 | `AGENTS.md` §1、`.specify/memory/constitution.md` 原则 V |
| 本增量范围 | 到 W5 为止：解析→清洗→分块→状态可查→失败重试；**向量化与问答留 002** | `specs/001-doc-ingest-pipeline/spec.md` |
| 数据模型 | 新增 `knowledge_bases` + `documents.kb_id`，查询按"用户 + 知识库"双过滤 | `docs/adr/0001-knowledge-base-entity.md`（已批准） |
| 支持格式 | PDF / DOCX / MD / TXT，单文件 ≤ 50MB，无 OCR | 同上 spec FR-015 / SC-009 |
| 失败重试 | 自动 2 次（指数退避）+ 手动至多 3 次，失败原因可读回写 | 同上 spec FR-008/009 |
| 知识库删除 | **非空拒删**（防与后台任务竞态），不做级联 | ADR-0001 |
| **文档删除**（第 2 组定） | **墓碑 + 级联双轨**：写 `documents.deleted_at` 墓碑 + 同事务物理删 chunks / processing_tasks；两表对 documents 的 FK 带 `ON DELETE CASCADE` 兜底。读取一律 `deleted_at IS NULL`，worker 写回前同事务复查墓碑 | findings D-024、任务 9.1 |
| **状态存放**（第 2 组定） | `documents.status` 是查询权威；`processing_tasks.stage` 供 8.3 卡死扫描（免 join）；**两者由单一状态迁移方法同事务成对写入**（6.4 落地） | findings D-025 |
| **处理任务粒度**（第 2 组定） | `processing_tasks.document_id` **唯一** —— 一文档恒一行，重试复用该行只累加计数（落实 5.3） | 迁移 `0001` / 任务 5.3 |
| **状态列类型**（第 2 组定） | `VARCHAR(20)` + 应用层枚举（**不用 PG 原生枚举**，免 ALTER TYPE 负担）；入库值 `uploaded/parsing/chunking/vectorizing/ready/failed`，中文文案由接口层翻译 | `app/models/enums.py` |
| **kb_id 外键**（第 2 组定） | `documents.kb_id → knowledge_bases.id` **不级联**（RESTRICT），是"非空拒删"的第二道闸门 | ADR-0001 / 迁移 `0001` |
| 目录布局 | 代码与规格直接放仓库根，不再嵌套 `docmind/` 层 | `AGENTS.md` §7 |
| Milvus | compose 中列为可选 profile，**本期默认不启动** | `design.md` D1/D9 与风险节 |
| 002 前置约束 | 建 `doc_chunks` collection 时**必须带 `kb_id` 字段** | ADR-0001 末节 |

澄清问答原文见 `specs/001-doc-ingest-pipeline/clarify-answers.md`；规格质量清单 16/16 通过。

---

## 五、工件地图

```
AGENTS.md                               AI 运行时规则（会话启动必读）
.env / .env.example                     真实密钥 / 可提交样例（.env 已被忽略）
backend/                                后端代码：app/{core,api,models,schemas,services,workers} + tests + alembic
    ├── app/core/config.py              配置系统（必需 3 / 占位 7 / 业务参数，缺必需项即失败）
    ├── app/core/errors.py              统一错误响应契约 {code, message, detail?}
    ├── app/core/db.py                  引擎 / 会话 / 连通性探测（失败写日志，HTTP 只回类型名）
    ├── app/api/routes/health.py        /health/live（不碰外部依赖）与 /health/ready（探 pg+redis）
    ├── app/models/                     ★任务 2.1：五张表
    │     ├── enums.py                  DocumentStatus + STATUS_SEQUENCE + 两表共用列类型
    │     ├── user.py                   用户名唯一 + 只存密码摘要
    │     ├── knowledge_base.py         含 uq_kb_user_name(user_id, name) 唯一索引
    │     ├── document.py               含 kb_id NOT NULL / deleted_at 墓碑 / chunk_count
    │     ├── chunk.py                  uq_chunks_document_chunk_index（D4 幂等兜底）
    │     ├── processing_task.py        document_id 唯一 + 两个重试计数 + last_run_at
    │     └── __init__.py               五表聚合导出（应用与 Alembic 共用 Base）
    ├── alembic.ini                     ★任务 2.2：**纯 ASCII**、不存连接串
    ├── alembic/env.py                  URL 取自应用配置；import app.models；compare_type=True
    ├── alembic/README                  迁移命令与两个坑
    ├── alembic/versions/0001_initial_schema.py   五张表初始 DDL（已生效，只增不改）
    ├── app/workers/celery_app.py       Celery 应用 + beat 心跳调度
    ├── app/workers/tasks.py            心跳任务
    └── tests/                          conftest（配置隔离 / 双客户端 / 测试库 schema 建销）
                                        test_config / test_health / test_error_contract / test_models
docker-compose.yml                      api / worker / beat / pg / redis / nginx；Milvus 走 milvus profile（默认不启动）
docker/nginx.conf                       反代 api；用 Docker 内置 DNS 按 TTL 重解析上游
.gitignore / .gitattributes             忽略规则（含 .env、.venv、.codebuddy、.workbuddy、fixtures/acceptance）
openspec 产物 ↓
openspec/config.yaml                     schema: spec-driven，语言 zh-CN
openspec/changes/add-doc-ingest-pipeline/
    ├── proposal.md                      Why / What Changes / Capabilities / Impact（DDL 变更标 BREAKING）
    ├── specs/user-auth/spec.md          账号注册、登录、数据归属（ADDED Requirements + 场景）
    ├── specs/knowledge-base/spec.md     知识库 CRUD、归属约束、非空拒删
    ├── specs/document-ingest/spec.md    上传受理、四格式与 50MB、异步管线、状态与进度、重试、删除级联
    ├── design.md                        D1–D10 技术决策 + 风险 + 迁移计划 + 开放问题
    └── tasks.md                         10 组 / 35 项实施清单（**1.1–1.6、2.1–2.2 已勾选并带完成证据**）
.specify/memory/constitution.md          项目宪法 v1.1.0（保护清单 / 技术栈 / 停机点）
specs/001-doc-ingest-pipeline/spec.md    W5 规格基线（19 FR / 9 SC / 5 US），冻结
docs/PROJECT_CONTEXT.md                  项目简报（已修正过期的模型名）
docs/task_plan.md                        周级计划与当前状态
docs/findings.md                         决策沉淀 D-001 ~ **D-027**
docs/progress.md                         进度流水（逐组证据，末尾是最新的「第 2 组」一节）
docs/notes.md                            teach 讲解笔记骨架（W5 起逐周填）
docs/adr/0001-knowledge-base-entity.md   DDL 变更决策（Approved）；**ADR-0002 待产出（JWT + 密码哈希库）**
docs/HANDOFF.md                          本文
docs/新会话提示词.md                      开工提示词（主提示词 + 3 个场景变体）
tools/gen_acceptance_corpus.py           验收语料生成器（确定性可重建）
fixtures/README.md                       语料清单与预期结果对照表
fixtures/acceptance/                     实际语料（已忽略，不入库）
.workbuddy/memory/                       跨会话记忆（MEMORY.md + 每日日志，已忽略）
```

---

## 六、模型网关实况（2026-09-12 实测，非文档推测）

`.env` 里配置的是**一个统一网关**（阿里云 MaaS，OpenAI 兼容），一个 `BASE_URL` + 一个 `API_KEY` 覆盖三个用途。

| 用途 | 模型 | 端点 | 实测结果 |
| --- | --- | --- | --- |
| 生成 | `deepseek-v4-pro-0813` | `{BASE_URL}/chat/completions` | 200 OK |
| 嵌入 | `qwen3.7-text-embedding` | `{BASE_URL}/embeddings` | 200 OK，**维度 1024**（与 Milvus `FLOAT_VECTOR(1024)` 一致，无需改规格） |
| 重排 | `qwen3.7-text-rerank` | `{host}/api/v1/services/rerank/text-rerank/text-rerank` | 200 OK |

**三条硬信息（写代码时直接用）：**

1. **重排不在 OpenAI 兼容路径下** —— `/compatible-mode/v1/rerank`、`/v1/rerank`、`/rerank` 全部 404。
   必须用 `.env` 里的 `RERANK_BASE_URL`（DashScope 原生路径）。
2. **重排的请求/响应格式与 OpenAI 无关**：

   ```jsonc
   // 请求
   {"model": "qwen3.7-text-rerank",
    "input": {"query": "苹果", "documents": ["...", "..."]},
    "parameters": {"top_n": 3, "return_documents": true}}
   // 响应
   {"output": {"results": [{"index": 0, "relevance_score": 0.8567, "document": {"text": "..."}}]},
    "usage": {...}, "request_id": "..."}
   ```

   （扁平 Cohere 风格请求体也能被接受，但建议按原生嵌套式写，语义更明确。）
3. **生成模型默认开启思考模式**：`max_tokens=16` 时 16 个 token 全被 `reasoning_tokens` 吃掉、
   `content` 返回空串。实现时必须显式控制思考模式与 `max_tokens`；低成本任务（grade 打分、
   query 改写）建议换 `deepseek-v4-flash-0731`（网关 `/models` 里可选）。

> 网关 `GET {BASE_URL}/models` 可返回全部可用模型（200+ 个，含 qwen / deepseek / kimi / glm 等系列），
> 换模型前先查这个列表，别猜模型名。
> **W5 全程不调用任何模型服务**：密钥缺失只告警、不阻断启动（任务 1.4）。

---

## 七、验收语料（已生成完毕）

重建命令（确定性，同一脚本版本产出同一批文件）：

```bash
.venv/Scripts/python.exe tools/gen_acceptance_corpus.py
```

实测结果（2026-09-12）：

| 文件 | 大小 | 自检结论 |
| --- | --- | --- |
| `docmind_manual_10mb.pdf` | **10.53 MB** / 114 页 | 文本层可抽取（656 字符/前 3 页）→ 用于 SC-001/002 |
| `docmind_manual.pdf` | 276 KB / 10 页 | 文本层正常 → SC-009 |
| `docmind_product_spec.docx` | 40 KB | — |
| `docmind_handbook.md` | 6.2 KB | 含参数速查表 |
| `docmind_course_notes.txt` | 1.3 KB | — |
| `scanned_no_text_layer.pdf` | 121 KB / 1 页 | **0 字符可抽取** ✓ 无文本层，应判失败 |
| `corrupted.pdf` | 152 KB | pypdf 报 `PdfStreamError` ✓ 应自动重试 2 次后失败 |
| `mislabeled_image.pdf` | 1 KB | 内容是 PNG、扩展名 .pdf，报 `invalid pdf header` ✓ |
| `empty.txt` | 0 B | 边界：0 字节 |
| `unsupported_sample.csv` | 10 B | 边界：不支持格式 |

语料正文围绕 DocMind 自身规格撰写（512/64、50/50、RRF 常数 60、重排保留 8、阈值 0.6/0.75/0.92、
50MB 上限等具体数字），**W7 的 20-query 评测集可直接基于这批语料出题，答案可客观核对**。

预期结果对照见 `fixtures/README.md`。

---

## 八、红线（违反即返工）

详见 `AGENTS.md` §2–§6 与 `.specify/memory/constitution.md`，要点：

- 检索管线（分块 / 混合检索 / RRF / 重排 / 压缩）、mini-agent、引用对齐、语义缓存**全部原生实现**；
  禁 LangChain RAG 链、禁 LlamaIndex；LangGraph 只做编排
- 核心算法（分块、RRF、引用对齐、语义缓存）**先写测试**
- 新依赖 / 改 DDL / 改 collection schema = 停机点，先写 ADR 等批
- 密钥不入 git；`alembic/versions/` 只增不改；`docs/task_plan.md` 不虚构进度
- 所有查询必须带 `user_id` 过滤，文档与检索另加 `kb_id` 过滤
- 澄清问题必须开发者本人回答，**禁止代答**
- **`skip` 不等于通过**：任何"依赖不可达就跳过"的用例，都要确认它真的 ran 过
- **`alembic.ini` 只写 ASCII**（本机 locale 是 GBK，非 ASCII 会让 alembic 直接崩）

---

## 九、建议下一个会话调用的 skills

| 场景 | 用哪个 |
| --- | --- |
| 逐项实施 tasks.md | `openspec-apply-change`（`.codebuddy/skills/`） |
| 中途需求变化 | `openspec-propose` / `openspec-update-change` |
| W5 完工归档 | `openspec-archive-change`（归档后 `openspec/specs/` 成为新的规格真相） |
| 写核心算法 | `test-driven-development` + `karpathy-guidelines` |
| 声称完工前 | `verification-before-completion` |
| 提交代码 | `commit`（或按 `AGENTS.md` §4 质量门禁流程） |
| 学新概念（teach） | 项目约定的 teach 流程 → 结论写进 `docs/notes.md` |

**不要再调用** `/speckit.*` 系列（已按 Q1 结论弃用）。

---

## 十、待办与风险

1. **密钥已在聊天中出现过** → 建议在网关侧轮换一次 `API_KEY`，然后只更新本地 `.env`。
   本文档与所有入库文件均未包含密钥（`.env` 已被 `.gitignore` 排除，可用 `git check-ignore -v .env` 复核）。
   数据库口令是本地开发默认值 `docmind_dev_pw`；**测试侧不要抄它**，`backend/tests/conftest.py` 会从 `.env` 派生。
2. **`.codebuddy/` 与 `.workbuddy/` 未入库**（含会话数据风险，且可由 `openspec update` 重建）。
   换机器时需重跑 `openspec init --tools codebuddy --language zh-CN`。
3. **`.specify/` 入库但已停用**，保留作历史与宪法来源；新会话不要被它误导回 spec-kit 流程。
4. **数据库现状（第 2 组后，2026-09-12）**：`docmind` 与 `docmind_test` 均已在 Alembic `0001`
   （5 张业务表 + `alembic_version`）。结构变更一律**新增修订文件**，验收方式照第 2 组：
   干净库上 `upgrade → downgrade base → upgrade` + `alembic check`。
   - **`docmind_test` 复位约定**：跑 pytest 会按 metadata 建/销表（保留 `alembic_version` 行），
     要用 alembic 验库前先 `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` 再 `upgrade head`
5. **可复现的建库/迁移命令**：

   ```bash
   docker exec docmind-pg psql -U docmind -d docmind -c "CREATE DATABASE docmind_test OWNER docmind"
   cd backend
   DATABASE_URL="postgresql+asyncpg://docmind:<口令>@127.0.0.1:5433/docmind_test" .venv/Scripts/alembic.exe upgrade head
   docker exec docmind-api alembic upgrade head      # 容器内迁移开发库
   ```
6. 未验证项：`RERANK_BASE_URL` 的 `parameters.top_n` 语义（返回条数）已实测有效，
   但 `top_n` 与 `return_documents` 之外的参数（如 `max_chunks_per_doc`）未测，W7 做重排时先小样验证。
7. **下一项的阻塞点**：后端依赖清单尚未引入 JWT 签发库与密码哈希库 —— 第 3 组（账号体系）会用到，
   属"新依赖"停机点，**必须先出 ADR-0002 等开发者批准**，不要自行选型。
8. **交给第 4 / 9 组的衔接点**：知识库的"文档数量"与"非空拒删"只能统计 `deleted_at IS NULL` 的行；
   删库前若该库只剩墓碑行，需先物理清除再删库，否则会被 `fk_documents_kb_id_knowledge_bases` 拦住。
9. **测试脚手架的两个陷阱**（第 2 组踩过，详见 `docs/findings.md` D-026 / D-027）：
   测试库连接串从 `.env` 派生（别抄口令）；pytest-asyncio 的事件循环必须 session 级，否则 session 作用域
   异步 fixture 会跨循环用连接、表现为"测试库不可达"的 skip。
