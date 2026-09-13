# DocMind 开发交接文档

**交接时间**：2026-09-13（第 5 次交接）
**交接范围**：W5 第 4 组知识库（4.1–4.2）已完成；**下一站是第 5 组文档上传与受理，无停机点阻塞**
**给下一个会话**：读完本文 + `AGENTS.md` 即可接手，不需要回溯聊天记录

---

## 一、当前状态（一句话）

第 4 组已完成并提交 —— 交付 4 个知识库接口（`GET/POST /api/knowledge-bases`、`PATCH/DELETE /api/knowledge-bases/{kb_id}`）；
`openspec list` → **13/35 tasks**、`validate --strict` 通过；
开发库 `docmind` 与测试库 `docmind_test` 仍在 Alembic **`0001`**（本组无 DDL 变更，`alembic check` → `No new upgrade operations detected.`）；
6/6 容器 healthy（pg 5433 / redis 6380 / nginx 8080），镜像重建实测 **1 分 26 秒**（D-034 的缓存修复持续生效）；
`pytest -q` → **92 passed, 0 skipped**（第 4 组开工前为 58）；
经 nginx 打真实请求跑 `tools/verify_knowledge_base_e2e.py` → **26/26 PASS**（含"查库核对"，不是只看接口状态码）。
**下一项第 5 组（上传与受理 5.1–5.5）预期零新依赖，可直接实施；只有 5.3 的分布式锁若引入新库才触发停机点。**

**本组交付清单**

| 类别 | 文件 |
| --- | --- |
| 新增（4） | `backend/app/schemas/knowledge_base.py`、`app/services/knowledge_base.py`、`app/api/routes/knowledge_bases.py`、`backend/tests/test_knowledge_base_api.py` |
| 新增（验收） | `tools/verify_knowledge_base_e2e.py` —— 经 nginx 真请求 + `docker exec docmind-pg psql` 查库核对 |
| 修改（1） | `backend/app/main.py`（挂载 knowledge_bases 路由） |
| 修改（文档） | `docs/progress.md`、`docs/findings.md`（D-035 / D-036 / D-037）、`docs/task_plan.md`、`openspec/.../tasks.md` |

> 提交前已按 `AGENTS.md` §4 走质量门禁：**两轴并行子代理审查**（Standards 轴对 AGENTS.md / constitution / 两个 ADR；Spec 轴对 `user-auth` 规格 + tasks 3.x）→ **无硬违规**；1 条判断题已修（e2e 脚本改为从 `.env` 读 `NGINX_HOST_PORT` / `TOKEN_EXPIRE_MINUTES`，不再写死 8080 / 86400）。完整结论见 `docs/findings.md` D-032。

**最近一次提交拓扑**

| 提交 | 内容 |
| --- | --- |
| （本组） | **第 4 组知识库落地（4.1–4.2）** |
| `b464f22` | docs: 交接材料补记 fc4623a（规格回写与构建缓存修复） |
| `fc4623a` | 规格回写（用户名规则 / 当前账号自省）+ 修镜像构建缓存 |
| `7a7e648` | 交接材料刷新到第 3 组完工状态（第 4 次交接） |
| `bb95bef` | 第 3 组账号体系落地（3.1–3.3）+ ADR-0002 批准与依赖 |
| `d9a1cb2` | 交接材料刷新到第 2 组完工状态（第 3 次交接） |
| `98735be` | 第 2 组数据模型与迁移落地（2.1–2.2）+ 修掉 3 个环境缺陷 |

---

## 二、下一步从哪开始

1. **第 5 组：文档上传与受理**（`tasks.md` 5.1–5.5）—— 预期零新依赖
   - `5.1` 上传：类型白名单、`MAX_UPLOAD_MB` 上限、落共享卷、写 `uploaded` 记录、投递任务后立即返回（SC-001：10MB PDF 2 秒内受理且期间服务仍响应）
   - `5.2` 归属约束：`kb_id` 必填 + 属主校验 —— **直接复用 `services/knowledge_base.py::get_owned_knowledge_base`**（它就是把 `id` 与 `user_id` 放同一条 WHERE，取不到即 404）
   - `5.3` 分布式锁：**若为此引入新库（如 redis 之外的东西）即为停机点，先写 ADR 等批**；本机 redis 已在，优先用它
   - `5.4` 片段反查 / `5.5` 列表与详情：都属于读取路径，注意**一律带 `deleted_at IS NULL`**（D-024）
2. **之后按 tasks.md 顺序**：6.x 后台管线 → 7.x 状态与进度 → 8.x 失败重试与中断补偿 → 9.x 删除清理 → 10.x 验收留档
3. **开发者已点头的跳步项**：`6.1 先写分块算法测试`（零新依赖、不碰模型服务）获准提前做，但按 tasks.md 属第 6 组，
   第 3 / 4 组期间**均未跳步**。下一个会话若想利用等待间隙可以动它
4. **5.x 落地后的一个收尾动作**：`backend/tests/test_knowledge_base_api.py` 里"造文档状态"用的是直接插库的桩
   （`_insert_document`，因为 5.x 之前没有上传接口）。5.x 完成后可评估是否改走真实上传接口 ——
   **不必强求**：那几个用例被测的是 4.x 的计数与拒删逻辑，不是"文档怎么来的"

---

## 三、本机环境速查（踩过的坑，务必先看）

| 坑 | 现象 | 对策 |
| --- | --- | --- |
| **Bash 工具 PATH 会被清空** | `ls`/`grep`/`dirname` 等 coreutils 报 `command not found`，npm shim 解析失败（曾误判 openspec 未安装） | 每条命令开头显式设置 PATH（见下） |
| `git.exe` 不在 PortableGit/bin | `git: command not found` | 需把 `.../PortableGit/versions/1.2.0/cmd` 加进 PATH |
| `tasklist` / `taskkill` 不在默认 PATH | `tasklist: command not found` | 需要时把 `/c/Windows/System32` 前置进 PATH |
| 沙箱只允许写工作区内 | 往 `C:\Users\ASUS\.workbuddy\...` 建 venv 静默失败（exit 0 但无目录） | 依赖装进项目内 `.venv/`（已在 .gitignore） |
| **PowerShell 工具不回显 stdout**（第 3 组复现） | 命令 exit 0 却看不到任何输出 | 需要看输出时用 Bash；必须用 PS 时只能看退出码 + 事后用只读命令核验 |
| **`docker.exe` 不在 PATH** | `docker: command not found` | Docker Desktop 装在 **`D:\Docker\App`**（非默认路径），把 `/d/Docker/App/resources/bin` 前置进 PATH |
| **本机没有 `curl`** | HTTP 探针全部失败 | 用 `backend/.venv/Scripts/python.exe` + httpx 打真实请求 |
| **裸 `python` 不在 PATH** | `python: command not found` | 一律写全路径（`backend/.venv/Scripts/python.exe`） |
| **本机无本地 PostgreSQL / psql** | 连不上库 | 数据库只能走 compose 起的 pg（宿主 `127.0.0.1:5433`）；查库用 `docker exec docmind-pg psql -U docmind -d <db> -c "..."` |
| **宿主端口已被别的项目占用** | `up` 后连错服务 | OneHub 占 8000/5432/6379；既有 Milvus（project `lk_ai`）占 9000-9001/9091/19530 → DocMind 用独立 project name `docmind` + pg 5433 / redis 6380 / nginx 8080 |
| **`docker compose ps` 报 healthy 不等于链路可用** | 六容器全绿但经 nginx 是 502 | 凡"链路通"的结论**必须打真实请求**验证 |
| nginx 只在启动时解析一次上游主机名 | api 容器重建换 IP 后 nginx 持续 502 | 已修：`docker/nginx.conf` 用 `resolver 127.0.0.11 valid=10s` + 变量化 `proxy_pass` |
| **同批并行编辑同一文件会丢改动** | 字段没落盘，worker/beat 反复重启 | 同一文件的编辑串行执行，改完复核内容 |
| **宿主端口映射被 Compose 覆盖**（自定义 host 名无法从宿主直连） | 宿主跑 alembic / pytest 连不上 `pg` | `.env` 里 host 用 `127.0.0.1:5433`（宿主视角），容器内由 compose 覆盖为 `pg:5432` |
| **`alembic.ini` 必须纯 ASCII** | 写 UTF-8 中文注释 → alembic 用 locale 编码（本机 GBK）读 ini，`UnicodeDecodeError` 直接退出 | ini 保持 ASCII；中文说明写进 `alembic/env.py`（.py 恒按 UTF-8 读） |
| **测试库连接串别抄口令** | 1.5 的 conftest 硬编码口令与 `.env` 不一致 → 所有库用例**静默 skip**（输出仍是"通过"） | 已改为从 `.env` 读 `POSTGRES_*` / `PG_HOST_PORT` 拼 `docmind_test`，`TEST_DATABASE_URL` 可覆盖。**skip ≠ 通过** |
| **pytest-asyncio 1.4 的事件循环** | session 作用域异步 fixture 跨循环用连接 → `Event loop is closed` / `AttributeError: 'NoneType' object has no attribute 'send'` | `pyproject.toml` 已固定 `asyncio_default_fixture_loop_scope` / `asyncio_default_test_loop_scope` = `session`，并加 `addopts = "-ra"` |
| **跑完 pytest 用 alembic 验库前要先复位** | `db_schema` fixture 按 metadata 建/销表，但保留 `alembic_version` 行 → `upgrade head` 变成空操作 | `docker exec docmind-pg psql -U docmind -d docmind_test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"` 再 `alembic upgrade head` |
| **探测函数别把异常压成类型名** | `check_database` 只回 `AttributeError`，掩盖了真实的 `Event loop is closed` | 已改为同时写日志（HTTP 响应仍只回类型名） |
| **重命令会被 SIGTERM 掐断**（第 3 组新增） | 前台 `pip install` / `docker build` / bash 里 `for` 循环逐个 `ls` 都会中招；表现为输出为空 + exit 1 | 一律后台跑（`run_in_background`）。**被掐断 ≠ 没执行**：pip 子进程可能仍在后台装完，事后用只读命令核实 |
| **被中断的 pip install 会把 venv 打残**（第 3 组新增） | site-packages 留下空壳目录 → `ImportError: cannot import name X from Y (**unknown location**)` | `unknown location` + `Y.__file__ is None` = 命名空间包遮住真包。诊断用「单进程脚本枚举 site-packages 顶层逐个 import」。修复：`mv .venv .venv.damaged` → 用系统解释器重建 → 装依赖 → 复测。**Windows 上 `--force-reinstall` 是坏选择**（卡在卸载阶段，实测 12 分钟无进展） |
| **换容器窗口里的写请求不可信**（第 3 组新增） | `up -d --build` 刚返回就发写请求，那一轮写的事务回滚了（接口 11/11 全绿，但库里没数据） | 写操作的端到端验收**等服务稳定再跑**；**"写入成功"必须以查库为准**，不能只看接口回 201 |

**统一 PATH 前缀（建议每条 Bash 命令都用）：**

```bash
export PATH="/d/Docker/App/resources/bin:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/cmd:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/d/nvm/nodejs:/usr/bin:/bin"
```

**已就绪的工具**

- `openspec` v1.11.0（`D:\nvm\nodejs` → nvm v24.9.0）
- git 2.55.0，全局身份 `Asize <3238075590@qq.com>`
- Docker Desktop（CLI 29.7.2 / daemon linux / compose v5.3.1）—— 已常驻 `docmind` 栈
- Alembic 已接入：宿主用 `backend/.venv/Scripts/alembic.exe`，容器内用 `docker exec docmind-api alembic upgrade head`
- **测试基线**：`cd backend && .venv/Scripts/python.exe -m pytest -q` → **58 passed, 0 skipped**
- **端到端基线**：`cd backend && .venv/Scripts/python.exe ../tools/verify_auth_e2e.py` → **11/11 PASS**（经 nginx）
- **两个虚拟环境，勿混用**：
  - 仓库根 `.venv/`（Python 3.13.14）—— **只用于生成验收语料**（`tools/gen_acceptance_corpus.py`）
  - `backend/.venv/`（Python 3.12.3，系统解释器 `D:\IDE\Python\Python312`，**第 3 组重建过一次**）—— 后端运行时与测试

---

## 四、已冻结的决策（不要再重新讨论）

| 项 | 结论 | 权威出处 |
| --- | --- | --- |
| 规格流程 | **OpenSpec 单主线**（`changes/` → apply → archive）；spec-kit 仅作 W5 启动文档，`/speckit.*` 已弃用 | `AGENTS.md` §1 |
| 本增量范围 | 到 W5 为止：解析→清洗→分块→状态可查→失败重试；**向量化与问答留 002** | `specs/001-doc-ingest-pipeline/spec.md` |
| 数据模型 | 新增 `knowledge_bases` + `documents.kb_id`，查询按"用户 + 知识库"双过滤 | ADR-0001（已批准） |
| 支持格式 | PDF / DOCX / MD / TXT，单文件 ≤ 50MB，无 OCR | 同上 spec FR-015 / SC-009 |
| 失败重试 | 自动 2 次（指数退避）+ 手动至多 3 次，失败原因可读回写 | 同上 spec FR-008/009 |
| 知识库删除 | **非空拒删**（防与后台任务竞态），不做级联 | ADR-0001 |
| 文档删除 | **墓碑 + 级联双轨**：写 `documents.deleted_at` + 同事务物理删 chunks / processing_tasks；FK 带 `ON DELETE CASCADE` 兜底。读取一律 `deleted_at IS NULL` | findings D-024 |
| 状态存放 | `documents.status` 是查询权威；`processing_tasks.stage` 供 8.3 卡死扫描；**两者由单一状态迁移方法同事务成对写入** | findings D-025 |
| 处理任务粒度 | `processing_tasks.document_id` **唯一** —— 一文档恒一行，重试复用该行只累加计数 | 迁移 `0001` |
| 状态列类型 | `VARCHAR(20)` + 应用层枚举（不用 PG 原生枚举）；入库值 `uploaded/parsing/chunking/vectorizing/ready/failed` | `app/models/enums.py` |
| kb_id 外键 | `documents.kb_id → knowledge_bases.id` **不级联**（RESTRICT），是"非空拒删"的第二道闸门 | ADR-0001 / 迁移 `0001` |
| **知识库接口**（第 4 组） | 越权访问他人知识库一律 **404**（不用 403 —— 403 会把"他人资源是否存在"变成可探测信息）；重命名是 **PATCH 语义**（未带 `description` 则保留原值，靠 `UNSET` 哨兵 + `model_fields_set` 区分"没传"与"传 null"）；名称**不归一小写**、长度上限取模型常量 `KB_NAME_MAX_LENGTH`（= DDL 的 128，不另设配置项）；列表的 `document_count` **只算 `deleted_at IS NULL`** | findings D-035 |
| 知识库删除顺序 | 计数为 0 时**先物理清除该库下的墓碑文档**（`chunks` / `processing_tasks` 随 `ON DELETE CASCADE` 走）**再删库**；否则墓碑行持有的 `kb_id` 会被 RESTRICT 外键拦住 | findings D-037 |
| **鉴权选型**（第 3 组） | **PyJWT `>=2.9`** 签发凭证 + **argon2-cffi `>=23.1`** 做密码哈希（argon2id，**不经 passlib**）；argon2 参数**不进 Settings**；**不改 DDL** | **ADR-0002（已批准）** |
| **凭证契约**（第 3 组） | payload 只放 `sub/iat/exp`；传输用 `Authorization: Bearer`；校验失败一律 401 且**不区分**过期/伪造；登录失败不区分"用户不存在/密码错误"，且**用户不存在时也跑一次假哈希**防时序侧信道 | ADR-0002 D4 |
| 目录布局 | 代码与规格直接放仓库根，不再嵌套 `docmind/` 层 | `AGENTS.md` §7 |
| Milvus | compose 中列为可选 profile，**本期默认不启动** | `design.md` D1/D9 |
| 002 前置约束 | 建 `doc_chunks` collection 时**必须带 `kb_id` 字段** | ADR-0001 末节 |

澄清问答原文见 `specs/001-doc-ingest-pipeline/clarify-answers.md`；规格质量清单 16/16 通过。

---

## 五、工件地图

```
AGENTS.md                               AI 运行时规则（会话启动必读）
.env / .env.example                     真实密钥 / 可提交样例（.env 已被忽略）
backend/
    ├── app/core/config.py              配置系统（必需 3 / 占位 7 / 业务参数，缺必需项即失败）
    ├── app/core/errors.py              统一错误响应契约 {code, message, detail?} + UnauthorizedError（3.3 新增）
    ├── app/core/db.py                  引擎 / 会话 / 连通性探测
    ├── app/core/security.py            ★3.1/3.2：argon2id 哈希 + 凭证签发/校验（纯函数，不碰 DB）
    ├── app/api/deps.py                 ★3.3：get_db_session + get_current_user（鉴权唯一入口）
    ├── app/api/routes/health.py        /health/live 与 /health/ready
    ├── app/api/routes/auth.py          ★3.1–3.3：POST /api/auth/register|login、GET /api/auth/me
    ├── app/api/routes/knowledge_bases.py  ★4.1/4.2：GET/POST /api/knowledge-bases、PATCH/DELETE /{kb_id}
    ├── app/schemas/auth.py             ★用户名归一化 + 密码强度校验 + 请求/响应模型
    ├── app/schemas/knowledge_base.py   ★4.1：名称「先 strip 再判长」+ 创建/重命名/响应模型
    ├── app/services/auth.py            ★注册 / 校验凭证（哈希走 asyncio.to_thread）
    ├── app/services/knowledge_base.py  ★4.1/4.2：归属校验唯一入口 get_owned_knowledge_base + 计数 + 非空拒删
    ├── app/models/                     5 张表（users / knowledge_bases / documents / chunks / processing_tasks）
    ├── alembic/versions/0001_initial_schema.py   五张表初始 DDL（只增不改）
    ├── tests/conftest.py               配置隔离 / 双客户端 / 测试库 schema / **Account + account_factory + two_accounts**
    ├── tests/test_config.py  test_health.py  test_error_contract.py  test_models.py
    ├── tests/test_security.py          ★3.1/3.2 算法层单测
    ├── tests/test_auth_api.py          ★3.1–3.3 接口层验收
    └── tests/test_knowledge_base_api.py  ★4.1/4.2 接口层验收（含越权与 RESTRICT 外键的机制层断言）
docker-compose.yml                      api / worker / beat / pg / redis / nginx；Milvus 走 milvus profile
docker/nginx.conf                       反代 api；用 Docker 内置 DNS 按 TTL 重解析上游
tools/gen_acceptance_corpus.py          验收语料生成器（确定性可重建）
tools/verify_auth_e2e.py                ★3.x 端到端验收（经 nginx 真实 HTTP）
tools/verify_knowledge_base_e2e.py      ★4.x 端到端验收（经 nginx 真实 HTTP + 查库核对）
openspec/changes/add-doc-ingest-pipeline/
    ├── proposal.md / specs/{user-auth,knowledge-base,document-ingest}/spec.md / design.md
    └── tasks.md                        10 组 / 35 项（**1.1–1.6、2.1–2.2、3.1–3.3 已勾选并带证据**）
specs/001-doc-ingest-pipeline/spec.md   W5 规格基线（冻结）
docs/PROJECT_CONTEXT.md                 项目简报
docs/task_plan.md                       周级计划与当前状态（已刷新到 13/35）
docs/findings.md                        决策沉淀 D-001 ~ **D-031**
docs/progress.md                        进度流水（逐组证据，末尾是最新的「第 3 组」一节）
docs/notes.md                           teach 讲解笔记骨架（W5 起逐周填）
docs/adr/0001-knowledge-base-entity.md  DDL 变更决策（Approved）
docs/adr/0002-auth-libraries.md         鉴权选型（**Approved**）
docs/HANDOFF.md                         本文
docs/新会话提示词.md                      开工提示词（主提示词 + 3 个场景变体）
```

---

## 六、模型网关实况（2026-09-12 实测，非文档推测）

`.env` 里配置的是**一个统一网关**（阿里云 MaaS，OpenAI 兼容），一个 `BASE_URL` + 一个 `API_KEY` 覆盖三个用途。

| 用途 | 模型 | 端点 | 实测结果 |
| --- | --- | --- | --- |
| 生成 | `deepseek-v4-pro-0813` | `{BASE_URL}/chat/completions` | 200 OK |
| 嵌入 | `qwen3.7-text-embedding` | `{BASE_URL}/embeddings` | 200 OK，**维度 1024**（与 Milvus `FLOAT_VECTOR(1024)` 一致） |
| 重排 | `qwen3.7-text-rerank` | `{host}/api/v1/services/rerank/text-rerank/text-rerank` | 200 OK |

**三条硬信息（写代码时直接用）：**

1. **重排不在 OpenAI 兼容路径下** —— `/compatible-mode/v1/rerank`、`/v1/rerank`、`/rerank` 全部 404。
   必须用 `.env` 里的 `RERANK_BASE_URL`（DashScope 原生路径）。
2. **重排的请求 / 响应格式与 OpenAI 无关**：

   ```jsonc
   // 请求
   {"model": "qwen3.7-text-rerank",
    "input": {"query": "苹果", "documents": ["...", "..."]},
    "parameters": {"top_n": 3, "return_documents": true}}
   // 响应
   {"output": {"results": [{"index": 0, "relevance_score": 0.8567, "document": {"text": "..."}}]},
    "usage": {...}, "request_id": "..."}
   ```
3. **生成模型默认开启思考模式**：`max_tokens=16` 时 16 个 token 全被 `reasoning_tokens` 吃掉、
   `content` 返回空串。低成本任务（grade 打分、query 改写）建议换 `deepseek-v4-flash-0731`。

> 网关 `GET {BASE_URL}/models` 可返回全部可用模型（200+ 个），换模型前先查这个列表，别猜模型名。
> **W5 全程不调用任何模型服务**：密钥缺失只告警、不阻断启动（任务 1.4）。

---

## 七、验收语料（已生成完毕）

重建命令（确定性，同一脚本版本产出同一批文件；注意这是**语料专用 venv**）：

```bash
.venv/Scripts/python.exe tools/gen_acceptance_corpus.py
```

实测结果（2026-09-12）：

| 文件 | 大小 | 自检结论 |
| --- | --- | --- |
| `docmind_manual_10mb.pdf` | **10.53 MB** / 114 页 | 文本层可抽取 → 用于 SC-001/002 |
| `docmind_manual.pdf` | 276 KB / 10 页 | 文本层正常 → SC-009 |
| `docmind_product_spec.docx` | 40 KB | — |
| `docmind_handbook.md` | 6.2 KB | 含参数速查表 |
| `docmind_course_notes.txt` | 1.3 KB | — |
| `scanned_no_text_layer.pdf` | 121 KB / 1 页 | **0 字符可抽取** ✓ 无文本层，应判失败 |
| `corrupted.pdf` | 152 KB | pypdf 报 `PdfStreamError` ✓ 应自动重试 2 次后失败 |
| `mislabeled_image.pdf` | 1 KB | 内容是 PNG、扩展名 .pdf ✓ |
| `empty.txt` | 0 B | 边界：0 字节 |
| `unsupported_sample.csv` | 10 B | 边界：不支持格式 |

预期结果对照见 `fixtures/README.md`。语料正文围绕 DocMind 自身规格撰写，W7 的 20-query 评测集可直接基于这批语料出题。

---

## 八、红线（违反即返工）

详见 `AGENTS.md` §2–§6 与 `.specify/memory/constitution.md`，要点：

- 检索管线（分块 / 混合检索 / RRF / 重排 / 压缩）、mini-agent、引用对齐、语义缓存**全部原生实现**；
  禁 LangChain RAG 链、禁 LlamaIndex；LangGraph 只做编排
- 核心算法（分块、RRF、引用对齐、语义缓存）**先写测试**
- 新依赖 / 改 DDL / 改 collection schema = 停机点，先写 ADR 等批（**ADR-0002 已批，不必重做**）
- 密钥不入 git；`alembic/versions/` 只增不改；`docs/task_plan.md` 不虚构进度
- 所有查询必须带 `user_id` 过滤，文档与检索另加 `kb_id` 过滤
- 澄清问题必须开发者本人回答，**禁止代答**
- **`skip` 不等于通过**：任何"依赖不可达就跳过"的用例，都要确认它真的 ran 过
- **`alembic.ini` 只写 ASCII**（本机 locale 是 GBK）
- **写操作的"成功"以查库为准**，不能只看接口回了 201
- **重命令（pip / docker build / 大套件 pytest）一律后台跑**，别赌前台时限

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

1. **两项"规格未规定"已定案**（2026-09-12 开发者本人作答）：用户名**区分大小写**（`alice` ≠ `Alice`）；密码**上限 128 字符**（配置 `PASSWORD_MAX_LENGTH`）。规格已同步更新，**不要再改**。
2. **审查记录的 3 项"规格未覆盖"已收口**（2026-09-13，开发者授权"按推荐来"，见 `docs/findings.md` D-034）：
   用户名"非空 / ≤64 / 忽略两端空白"与 `GET /api/auth/me` 两项**已回写进 `user-auth` 规格**（新增「当前账号自省」Requirement）；
   3.3 越权**写**操作的 defer **保持现状**（4.1 / 5.2 的验收本身就含跨账号用例）。**不需要再动。**
3. **`SECRET_KEY` 轮换 = 全体凭证立即失效**：本期单密钥、无 kid / 双密钥并存机制。属开发期可接受取舍，换密钥时要心里有数。
4. **无 lockfile**：依赖解析不可重现（同一份 `pyproject.toml` 在不同时间装出的版本可能不同）。
   与 ADR-0002 同批发现，超出该 ADR 范围，**建议单独立项**。
5. **密钥已在聊天中出现过** → 建议在网关侧轮换一次 `API_KEY`，然后只更新本地 `.env`。
   数据库口令是本地开发默认值；**测试侧不要抄它**，`backend/tests/conftest.py` 会从 `.env` 派生。
6. **`.codebuddy/` 与 `.workbuddy/` 未入库**：换机器时需重跑 `openspec init --tools codebuddy --language zh-CN`。
7. **`.specify/` 入库但已停用**：保留作历史与宪法来源；新会话不要被它误导回 spec-kit 流程。
8. **数据库现状**：`docmind` 与 `docmind_test` 均在 `0001`（本组无 DDL 变更）。结构变更一律**新增修订文件**，
   验收方式照第 2 组：干净库上 `upgrade → downgrade base → upgrade` + `alembic check`。
9. **交给第 9 组的衔接点**：知识库的"文档数量"与"非空拒删"只统计 `deleted_at IS NULL` 的行
   —— **第 4 组已按此实现并落地**（`services/knowledge_base.py`，且删除时会先物理清墓碑，见 D-037）。
   第 9 组做"删除文档"时仍需遵守同一口径：写墓碑 + 同事务物理删 `chunks` / `processing_tasks`，读取一律 `deleted_at IS NULL`。
10. **可复现的建库 / 迁移命令**：

    ```bash
    docker exec docmind-pg psql -U docmind -d docmind -c "CREATE DATABASE docmind_test OWNER docmind"
    cd backend
    DATABASE_URL="postgresql+asyncpg://docmind:<口令>@127.0.0.1:5433/docmind_test" .venv/Scripts/alembic.exe upgrade head
    docker exec docmind-api alembic upgrade head      # 容器内迁移开发库
    ```
11. **未验证项**：`RERANK_BASE_URL` 的 `parameters.top_n` 语义已实测有效，但 `max_chunks_per_doc` 等参数未测，
    W7 做重排时先小样验证。
12. **镜像构建已加缓存 —— 实测生效（2026-09-13）**：`backend/Dockerfile` 去掉 `PIP_NO_CACHE_DIR=1`，
    并给 pip 的 `RUN` 加 `--mount=type=cache,target=/root/.cache/pip`（细节见 `docs/findings.md` D-033 / D-034）。
    实测同一台机器：修复前改 `app/` 重建 **41 分 37 秒** → 修复后 **1 分 27 秒**
    （判据是同一次构建日志里 `Downloading` 0 行 / `Using cached` 115 行，不是耗时——耗时会被网络带偏）。
    **首次**构建（缓存为空）仍需全量下载。若某环境 compose 用旧 builder 不认 `--mount`，回退那一行即可。
