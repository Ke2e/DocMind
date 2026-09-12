# findings.md — 决策与调研沉淀

> planning 三件套之一（决策）。架构级决策的详细论证另存 `docs/adr/`。

## 2026-09-10

### D-001 规格工作流选型：spec-kit 已初始化，主线待定
- **事实**：本机已装 spec-kit CLI v1.0.1；已在仓库根执行 `specify init --here --integration codebuddy --ignore-agent-tools`，生成 `.specify/`（模板 + ps 脚本）与 `.codebuddy/commands/speckit.*.md`。
- **冲突**：`PROJECT_CONTEXT.md` 第 7 节任务 0 写的是 OpenSpec（`changes/` 提案流），本次开发者点名 spec-kit `/specify`。
- **待定**：Q1（spec-kit 单主线 / 双轨 / 回退 OpenSpec）。

### D-002 特性编号与目录
- `feature_numbering = sequential`，首个特性目录 `specs/001-doc-ingest-pipeline`（文档摄取管线 = W5 切片）。
- `.specify/feature.json` 已指向该目录，供后续 plan/tasks 定位。

### D-003 目录布局假设
- 代码与规格直接放仓库根，不再嵌套 `docmind/` 一层（`PROJECT_CONTEXT.md` 第 4 节的树以 `docmind/` 为根，实为仓库根）。
- 未经开发者确认，可推翻。

### D-004 Constitution 来源
- `.specify/memory/constitution.md` 由 `PROJECT_CONTEXT.md` 第 8 节转写（保护清单 / 技术栈 / 停机点 / 质量门禁），v1.0.0，待开发者审阅。

### D-005 仓库尚未 git 初始化
- `specify init` 未创建 git 仓库。spec-kit 的分支钩子与版本管理需要 git；是否 `git init` 待开发者决定。

## 2026-09-12（澄清答案落地）

### D-006 规格主线定为 OpenSpec（Q1=C）
- spec-kit 只作 W5 启动文档：`specs/001-doc-ingest-pipeline/spec.md` 冻结为 W5 规格基线，`/speckit.plan`、`/speckit.tasks` 不再使用。
- 后续功能变更与 RAG 参数迭代走 `openspec/changes/` 提案流。已同步 constitution 原则 V（v1.1.0）与 AGENTS.md §1、§7。
- 代价：放弃 spec-kit 的 plan/tasks 工具链；收益：与既有项目文档一致，不引入第二套流程。

### D-007 001 范围锁定在 W5（Q2=A）
- 分块完成即"完成"；状态机保留"向量化"位但不启用，向量化 + 问答入 002。

### D-008 引入 knowledge_bases（Q3=B，DDL 变更）
- 详见 `docs/adr/0001-knowledge-base-entity.md`（Proposed，待批）。
- 关键衍生约束：**002 建 Milvus collection 时必须带 `kb_id` 字段**，否则向量层无法做知识库过滤。此项要写进 002 的规格输入。
- 删除非空知识库采用"拒绝"而非级联，避免与后台写入任务竞态。

### D-009 支持格式与上限（Q4=A）
- PDF / DOCX / MD / TXT，单文件 ≤ 50MB；无 OCR，无文本层按失败处理。
- 解析器在既定技术栈内（pypdf / python-docx / markdown），**无新增依赖**。

### D-010 重试策略（Q5=A）
- 自动 2 次（指数退避）+ 手动至多 3 次，合计上限可配置；失败原因写回可读文本。
- 需要 Processing Task 记录自动/手动两个计数器（已入 Key Entities）。

### D-011 OpenSpec CLI 可用（此前误判）
- `openspec` v1.11.0 **已全局安装**：`D:\nvm\nodejs` 是指向 `D:\nvm\nvm\v24.9.0` 的链接，`@fission-ai/openspec` 在其中。
- 早前判为"未安装"是**探测失误**：沙箱 bash 的 PATH 被清空，导致 shim 脚本里的 `dirname`/`sed`/`uname` 全部找不到，`basedir` 退化成空串，模块路径被拼成 `e:\node_modules\...` → 报 MODULE_NOT_FOUND。
- **教训**：在这台机器上跑命令时，先 `export PATH="/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/d/nvm/nodejs:/usr/bin:/bin"`，否则 coreutils 与 node 全局命令都不可用。
- 已执行：`openspec init . --tools codebuddy --language zh-CN --no-animation --force`，生成 `openspec/config.yaml`（schema: spec-driven，语言 zh-CN）、`.codebuddy/commands/opsx/*`、`.codebuddy/skills/openspec-*`。root `AGENTS.md` 未被改写（已 diff 验证）。

### D-012 W5 change 提案已产出并通过校验
- `openspec/changes/add-doc-ingest-pipeline/`：proposal.md、specs/{user-auth,knowledge-base,document-ingest}/spec.md、design.md、tasks.md。
- `openspec validate add-doc-ingest-pipeline --strict` → valid；`openspec status` → 4/4 artifacts complete；`openspec list` → 0/32 tasks。
- 能力划分：三个新能力（账号 / 知识库 / 摄取），互不重叠；DDL 变更在 proposal 中标 **BREAKING** 并在 design 的 D2/D3/D4/D8 给出取舍。
- ADR-0001 由开发者批准（2026-09-12），已回写 spec.md Dependencies。

### D-013 模型与密钥分工核实（2026-09-12，查官方文档）
- **两个密钥对应两个服务商，各管一半**：
  - `DEEPSEEK_API_KEY`（`https://api.deepseek.com`）→ **只做生成**（回答生成、query 改写、grade 打分、verify 判定），OpenAI 兼容
  - `SILICONFLOW_API_KEY`（`https://api.siliconflow.cn/v1`）→ **嵌入 + 重排**，同一 key 用于 `/v1/embeddings`（`BAAI/bge-m3`，1024 维）与 `/v1/rerank`（`BAAI/bge-reranker-v2-m3`，接口格式同 Cohere，非 OpenAI 端点）
- **DeepSeek 官方不提供 embedding 与 rerank 模型**（模型表只有 `deepseek-flash` 与 `deepseek-v4-pro` 两个文本模型）。RAG 的"生成"与"表示/排序"本就是两类模型，第二家是刚需而非可选。
- **文档纠错**：`docs/PROJECT_CONTEXT.md` 原写"DeepSeek-V3"已过期——现官方模型 ID 为 `deepseek-flash`（= DeepSeek-V4.1-Flash）与 `deepseek-v4-pro`；`deepseek-chat` / `deepseek-reasoner` 已下线，新代码用旧名会直接报错。已修正该行，并让 tasks.md 1.4 把 base_url 与模型 ID 写进配置样例。
- **成本提示**：DeepSeek 高峰时段（周一至周五 9:00-12:00、14:00-18:00）单价翻倍 → W7/W10 的批量评测放在空闲时段跑。

### D-014 实际网关是「一家统一网关」，不是两家服务商（2026-09-12 以 `.env` 为准修正）
- 开发者在 `.env` 中配置的是**一个阿里云 MaaS 聚合网关**（OpenAI 兼容）：一个 `BASE_URL` + 一个 `API_KEY` 同时提供生成 / 嵌入 / 重排。D-013 里"DeepSeek + 硅基流动两家"是通用情况，本项目按实际配置执行。
- 实测（全部 200）：
  - 生成 `deepseek-v4-pro-0813` @ `{BASE_URL}/chat/completions`
  - 嵌入 `qwen3.7-text-embedding` @ `{BASE_URL}/embeddings` → **维度 1024，与 Milvus `FLOAT_VECTOR(1024)` 天然一致，无需改规格**
  - 重排 `qwen3.7-text-rerank` @ `{host}/api/v1/services/rerank/text-rerank/text-rerank`
- **重排不在 OpenAI 兼容路径下**：`/compatible-mode/v1/rerank`、`/v1/rerank`、`/rerank` 全部 404；必须用 DashScope 原生路径，故配置拆出 `RERANK_BASE_URL`。请求体 `{model, input:{query,documents}, parameters:{top_n,return_documents}}`，响应取 `output.results[].relevance_score`。
- **生成模型默认思考模式**：`max_tokens` 过小会把额度全耗在 `reasoning_tokens` 上、`content` 返回空串（实测 16 token 全被吃掉）。实现时须显式控制思考模式与 `max_tokens`。
- 网关 `GET {BASE_URL}/models` 可列出全部可用模型（200+），换模型前先查列表。

### D-015 验收语料改为脚本生成（不入库）
- `tools/gen_acceptance_corpus.py` 确定性生成 10 个文件到 `fixtures/acceptance/`；该目录已 gitignore（含 10.53MB PDF，不宜入库）。
- 用 pypdf 做机器自检：正常 PDF 文本层可抽取、扫描件 0 字符、损坏文件报错——三条都符合预期。
- 语料正文即 DocMind 自身规格（512/64、50/50、RRF 常数 60、阈值 0.6/0.75/0.92、50MB），W7 的 20-query 评测集可直接复用。

### D-016 git 仓库已建立
- `git init -b main`，首次提交 `d34b36b`，43 个文件入库。
- `.gitignore` 排除：`.env`、`.venv/`、`.codebuddy/`、`.workbuddy/`、`fixtures/acceptance/`、Python/Node 产物；已用 `git check-ignore -v` 逐条核验命中。

### D-017 周计划确认（2026-09-12，停机点 2 通过）
开发者逐条确认 32 项计划，并拍板四个待定项：

| 待定项 | 结论 |
|---|---|
| 计划增补 | **全部采纳** → tasks.md 由 32 项变 **35 项** |
| 宿主端口 | **独立端口**：pg 5433 / redis 6380 / nginx 8080，api 容器内 8000 不映射宿主 |
| 同库文档同名 | **允许**（靠 doc id 区分，不加唯一约束 → 不触发 DDL 停机点） |
| 注册密码强度 | 长度 **≥8 且同时包含字母与数字**（阈值可配置，写入 user-auth spec） |

增补明细：新增 1.5 测试脚手架、1.6 统一错误契约、5.4 片段反查接口；原 4.3（文档归属约束）移入第 5 组；1.4 补全业务参数外置清单；6.2 验证口径改写；10.2 改为逐组回写证据。

### D-018 为什么这 3 项必须新增任务（不是可选项）
- **1.5 测试脚手架**：6.1 要求"先写测试"、3.x–5.x 的验收方式全是"接口测试"，但原计划没有任何一项建 pytest 脚手架 → 后续任务的"验证方式"无处落地。
- **1.6 错误响应契约**：7.2 要求"响应不含堆栈或内部实现细节"，没有统一出口无法逐处保证 → 定为 `{code, message, detail?}`，并覆盖框架默认 404 / 422。
- **5.4 片段反查接口**：FR-005 与 document-ingest spec 的"反查片段"场景要求按文档反查全部片段，原 5.3 只做列表与详情（含数量）→ 缺接口。
- **顺序修正**：原 4.3 验的是"上传时的 kb_id 归属校验"，而上传接口到 5.1 才存在 → 无法先验。

### D-019 6.2 的验收判据与重叠参数自相矛盾（口径修正）
默认 512 / 重叠 64 时，相邻片段**必然**共享边界文本，"拼接后与原文比对无丢字"隐含"无重复"，与 overlap 直接冲突（SC-006 的"无重复段"同样歧义）。判据改为三项：**覆盖性**（原文每个 token 位置至少被一个片段包含）/ **顺序性**（按 `chunk_index` 升序与原文一致）/ **忠实性**（每个片段是原文的连续子串）。SC-006 的"无重复段"据此解释为"无重复片段"，而非"文本不重复"。已写入 design.md D5。

### D-020 本机 Docker 与端口冲突实测（2026-09-12）
- Docker Desktop 装在 **`D:\Docker\App`（非默认路径）**，CLI 29.7.2，daemon 正常（linux 容器），compose v5.3.1；`docker.exe` 不在 PATH，需把 `/d/Docker/App/resources/bin` 加进去。
- 宿主端口占用：OneHub 栈占 **8000 / 5432 / 6379**；既有 Milvus（compose project `lk_ai`）占 **9000-9001 / 9091 / 19530** → DocMind 用独立 project name `docmind` 并错开端口。
- 本机**无本地 PostgreSQL、无 psql**，也**无 `curl`** → 后端验证改用 venv 内 httpx 发真实 HTTP 请求。

### D-021 `.env` 原先缺三个必需项
- 实测 `.env` 只有 7 个模型网关键，缺 `DATABASE_URL` / `REDIS_URL` / `SECRET_KEY` → 按 1.4 的设计应用会拒绝启动，compose 也无法建库。
- 按开发默认值追加（**仅追加缺失键，原 7 行未改动**）：`POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`、`PG_HOST_PORT=5433`、`REDIS_HOST_PORT=6380`、`NGINX_HOST_PORT=8080`、`DATABASE_URL`、`REDIS_URL`、`SECRET_KEY`（32 字节随机）。`.env` 仍被 gitignore，`git check-ignore -v .env` 复核通过。
- 一份 `.env` 服务两个场景：容器内由 compose 把 host 覆盖为服务名（pg:5432 / redis:6379），宿主侧直连走 127.0.0.1:5433 / 6380。

### D-022 Python 版本与虚拟环境
- 后端必须 Python 3.12（技术栈锁定）→ 用系统解释器 `D:\IDE\Python\Python312`（3.12.3）建 **`backend/.venv`**（gitignore 命中）。
- 仓库根原有 `.venv`（3.13.14）**只用于生成验收语料**，与后端运行时无关，两个环境不要混用。

### D-023 编排与工具链的三个真实坑（2026-09-12 实测踩到并修掉）

**1. nginx 只在启动时解析一次上游主机名** —— 首次 `up` 后 `api` 容器 IP 为 172.20.0.6；第二次 `up --build` 重建 api 后 IP 变化，nginx 仍连旧 IP，于是**对外持续 502**。
- 修法：`docker/nginx.conf` 声明 Docker 内置 DNS 并变量化 `proxy_pass`，强制按 TTL 重新解析：
  ```nginx
  resolver 127.0.0.11 valid=10s ipv6=off;
  location / { set $upstream_api http://api:8000; proxy_pass $upstream_api; }
  ```
- **配套教训：容器自报 `healthy` 不等于对外链路可用**。当时 `docker compose ps` 六个容器全绿，但经 nginx 打真实请求是 502——nginx 的健康检查已连续失败，只是还没跑满 `retries: 12 × 10s` 没翻成 unhealthy。**凡"链路可用"的结论，必须打真实请求验证，不能只看容器状态。**

**2. Celery `-A` 的写法** —— `-A app.workers.celery_app` 依赖 Celery 回退扫描模块变量找 Celery 实例（能找到但不明确）；显式写 `app.workers.celery_app:celery_app` 更稳，已统一。健康检查命令同理。

**3. beat 没有内置健康端点** —— 用「心跳任务写进 Redis 的键是否还在」做探针：beat 每 `BEAT_HEARTBEAT_INTERVAL_SECONDS` 触发 `beat_heartbeat`，worker 执行后 `SETEX docmind:beat:heartbeat`（TTL = 3 个周期）。这一条探针同时覆盖 beat → broker → worker → redis 整条链路，比 `kill -0 1` 之类的进程级伪探针有意义。

**4. 同批并行编辑同一文件会丢改动** —— 给 `config.py` 加 `BEAT_HEARTBEAT_INTERVAL_SECONDS` 的编辑与另一处编辑同批提交，前者未落盘，导致 worker / beat 反复重启（`'Settings' object has no attribute 'BEAT_HEARTBEAT_INTERVAL_SECONDS'`）。**规则：同一文件的编辑串行执行，改完必须复核内容。**

## 2026-09-12（第 2 组：数据模型与迁移）

### D-024 文档删除走"墓碑 + 级联"双轨（2.1 落地 design D8 / 任务 9.1）

- **问题**：9.1 同时要求"级联清除派生数据"和"删除标记阻止写回"，而两条单独用都有缺口——纯物理删除挡不住已开工的 worker 写回（它手里还攥着 document_id）；纯软删除又会与"知识库非空拒删"打架（墓碑行仍持有 `kb_id`，外键会拦住删库）。
- **结论**：`documents.deleted_at` 作墓碑。删除请求在同一事务内：(1) 写墓碑；(2) 物理删该文档的 `chunks` 与 `processing_tasks`；(3) 两张表对 `documents` 的外键带 `ON DELETE CASCADE` 兜底，覆盖"知识库删除时清墓碑"这类后续物理清除。所有读取一律 `deleted_at IS NULL`；worker 每次写回前在同一事务内复查墓碑，命中即放弃写入。
- **衍生约束（交给第 4 / 9 组）**：知识库的"文档数量"与"非空拒删"都只统计 `deleted_at IS NULL` 的行；删库前若该库只剩墓碑行，需先物理清除再删库，否则会被 `fk_documents_kb_id_knowledge_bases` 拦住（该外键刻意保持默认 RESTRICT，是"非空拒删"的第二道闸门）。

### D-025 状态为什么存两份（`documents.status` 与 `processing_tasks.stage`）

- **冲突**：design D3 写的是"`documents.status` 存当前阶段、任务记录只存计数与时间"，而冻结的 `spec.md` Key Entities 把"当前阶段"列在 Processing Task 上。
- **取舍**：两份都留，但把"同事务成对写入"定为硬约束（由 6.4 的单一状态迁移方法负责，禁止别处改状态）。保留 `stage` 的实际收益是 8.3 的卡死扫描可按"中间态 + `last_run_at` 超阈值"在单表筛完，不必 join。
- 同时 `processing_tasks.document_id` 建**唯一约束**：既落实 5.3"并发提交同一文档只产生一条处理记录"，也让重试复用同一行、只累加计数。

### D-026 两个环境级坑（2026-09-12 实测踩到并修掉）

**1. `alembic.ini` 必须纯 ASCII** —— alembic 用 locale 编码读该文件，中文 Windows 下是 GBK，写 UTF-8 中文注释会让 CLI 直接 `UnicodeDecodeError` 退出。规则：ini 保持纯 ASCII，中文说明写进 `alembic/env.py`（.py 恒按 UTF-8 读）。

**2. 1.5 的测试库连接串口令与 `.env` 不一致 → 用例静默降级为 skip** —— conftest 里硬编码的测试库口令是 `docmind`，而 PG 容器是按 `.env` 的 `docmind_dev_pw` 建的；于是所有依赖 `db_engine` 的用例都会 `pytest.skip`：**输出仍是"通过"，但一条库断言都没跑**。1.5 当时没有用到库的用例，所以没暴露。
- 已修：从仓库根 `.env` 读 `POSTGRES_*` / `PG_HOST_PORT` 拼测试库连接串（口令只留一份来源），并支持 `TEST_DATABASE_URL` 覆盖；`setdefault` 改成直接赋值，避免外部残留的 `DATABASE_URL` 把测试带偏。
- **教训：`skip` 不等于通过。**脚手架里任何"库不可达就跳过"的降级路径，都会在口令/端口配错时伪装成绿灯；第 3 组起有库断言后，必须确认用例是 **ran** 而不是 **skipped**。

### D-027 pytest-asyncio 1.4 的默认事件循环与 session 作用域 fixture 冲突（2.2 实测踩到并修掉）

- **现象**：新增的"在真实测试库按 metadata 建表"用例被 **skip**，原因是 `check_database` 返回"数据库不可用：AttributeError"；同时 pytest 抛 `RuntimeWarning: coroutine 'Connection._cancel' was never awaited`。
- **定位过程**：① 宿主用纯脚本直连测试库 → **成功**（排除 asyncpg / 网络 / 口令）；② 写临时用例对比函数作用域与 session 作用域 → **函数作用域通过、session 作用域 ERROR**，真实栈为
  `RuntimeError: Event loop is closed` → `AttributeError: 'NoneType' object has no attribute 'send'`（ProactorEventLoop 随循环一起关了）。
- **根因**：pytest-asyncio **1.4** 默认为每个用例创建函数级事件循环，而 `db_engine` 是 session 作用域异步 fixture——连接池里的连接在 A 循环建立、在 B 循环使用并关闭。
- **修法**：`pyproject.toml` 固定 `asyncio_default_fixture_loop_scope = "session"` 与 `asyncio_default_test_loop_scope = "session"`（全测试共用一个循环）；另加 `addopts = "-ra"` 强制汇总 skip。
- **附带改进**：`check_database` / `check_redis` 现在会把异常类型 + 原始消息写进日志（HTTP 响应仍只回类型名，不泄漏连接串）。原实现把 `Event loop is closed` 压成一个 `AttributeError`，害我一度误判为"测试库不可达"。
- **教训**：本机 pytest / pytest-asyncio 是 9.1.1 / 1.4.0 的新版本，行为与老教程不同；凡"跳过"都必须追到底，不能当作环境问题放过。

## 2026-09-12（第 3 组开工前的停机点）

### D-028 鉴权选型出 ADR（待批）——PyJWT + argon2-cffi

- **产出**：`docs/adr/0002-auth-libraries.md`（Proposed）。建议 **PyJWT**（`pyjwt>=2.9`）+ **argon2-cffi**（`argon2-cffi>=23.1`，直接用、不经 passlib）。
- **为什么不改 DDL**：`password_hash VARCHAR(255)` 是任务 2.1 按 argon2id 输出（约 97 字符）预留的；选 argon2id 与模型设计一致 → 不触发第二次 DDL 停机点。**这也是选型与 2.1 强耦合的原因**，若改选 bcrypt（60 字符）虽仍装得下，但会让这条预留失去意义。
- **参数不进配置**（D2）：argon2id 的 `time_cost` / `memory_cost` 做成 `Settings` 环境变量只会给人"调小一点跑得快些"的机会，而调小直接削弱抗爆破强度 → 定为代码常量；测试若嫌慢，用依赖注入换低开销 profile。
- **配套约定同时定下**（D4，免得 3.x 各写各的）：payload 只放 `sub/iat/exp`（不放 `username`/`role`，凭证字段越多越容易被当权限用）；校验失败一律 401 且不区分"过期"与"伪造"；**用户不存在时也要跑一次假哈希**，否则"响应快 = 用户不存在"就是时序侧信道。
- **算法白名单是红线**：`jwt.decode(..., algorithms=[settings.JWT_ALGORITHM])`，绝不 `algorithms=None`、绝不拿 header 里的 `alg` 当依据——2024 年 python-jose 的算法混淆漏洞（CVE-2024-33663）就是这么来的。

**选型类事实必须查上游，不能凭记忆**（本次踩到的自省）：

- 我最初准备把 python-jose 打成"带未修 CVE 的库"，**这是错的**：CVE-2024-33663 / 33664 在 **3.4.0 已修**（GHSA-6c5p-j8vq-pqhj），现行 3.5.0 不受影响。否决它的正当理由只能是"历史 CVE 记录 + extras 后端易在运行时暴露"，不是"现在还有洞"。
- 对照事实全部用可复现命令取：`pypi.org/pypi/<pkg>/json` 取版本与**发布日期**（passlib 停在 **2020-10-08**，这才是"停更"的硬证据），上游 issue/bug 编号佐证兼容性；`pip install --dry-run` / `pip download` 验完整依赖闭包与 wheel 形态。
- **教训**：涉及"某库是否安全 / 是否维护"的判断，凭印象写进 ADR 等于把错误固化进决策文档。发布日期、CVE 修复版本号、wheel 文件名这三类东西都必须现查。

**镜像侧未验证项**（已写进 ADR）：本机只验了 Windows wheel，`python:3.12-slim` 上的 manylinux wheel 未实测 → 批准后须 `docker compose up -d --build` 并进容器 `import jwt, argon2` 复核；若需编译则为新的构建依赖，要回头更新 ADR。

## 2026-09-12（第 3 组实施：账号体系）

### D-029 一次 pip 中断把 venv 打残了半个 —— 现象、诊断与修复

**触发**：前台跑 `pip install -e ".[dev]"`（第 3 组新增依赖）时被 SIGTERM 打断，输出为空、exit 1。
（沙箱对重命令有时限；pip 又恰好落在"卸旧装新"的中间态。）

**现象**：先是 `from argon2 import PasswordHasher` → `ImportError: cannot import name 'PasswordHasher' from 'argon2' (unknown location)`，
接着连 `from fastapi import FastAPI` 也是 `unknown location`。

**关键识别信号**：`unknown location` + `module.__file__ is None` = **命名空间包**。
实测 `argon2.__path__` 指向 site-packages 里那个目录、`__file__` 为 None —— 该目录只剩空壳（缺 `__init__.py`），真包被它遮住了。
**以后见到 `cannot import name X from Y (unknown location)`，第一步就去看 `Y.__file__` 是不是 None。**

**范围**：写一个全量探测脚本（枚举 site-packages 顶层条目，逐个 import，看 `__file__`）——比逐个猜快得多。
结果 **9 个包不可用**（fastapi / pydantic_settings / asyncpg / alembic / celery / python-docx / uvicorn / anyio / annotated_types）。
用 `ls` + bash for 循环做整目录体检反而被 SIGTERM 打断——**这种体检要用单进程脚本，不要用 shell 循环逐个 `ls`**。

**两个过程性教训**：

1. **中断 ≠ 未执行**：第一次探测与第二次探测结果不一致（第二次多出几个包能导入），说明被 SIGTERM 的 pip 子进程**还在后台继续装**。
   与 `d9a1cb2` 那次"commit 审批超时但提交其实已落库"是同一类教训 —— 事后必须用只读命令核实真实状态。
2. **Windows 上 `--force-reinstall` 是坏选择**：它要先把所有包卸载再装，实测卡在卸载阶段 **12 分钟无任何进展**（日志 mtime 不动），只能主动终止。
   该环境下杀软 + 海量小文件删除/写入极慢。

**最终有效的修复路径**（顺序照做即可）：

```bash
# 1) 把损坏的 venv 重命名挪开（不直接删，留退路）
mv backend/.venv backend/.venv.damaged-YYYYMMDD
# 2) 用系统解释器重建（本机 3.12.3）
"D:/IDE/Python/Python312/python.exe" -m venv backend/.venv
# 3) 装依赖（**走缓存**，别加 --no-cache-dir）；重活一律后台跑
cd backend && .venv/Scripts/python.exe -m pip install -e ".[dev]"
# 4) 全量探测确认 67/67 可导入，再删掉那个挪走的旧 venv
```

重建后实测：`pip install -e ".[dev]"` 7 分钟 exit 0，site-packages 顶层 67 个包 **67/67 可导入**。

**新增的机器级规则**：`pip install` / `docker build` / 大套件 pytest 一律用后台任务跑，不要赌前台时限。

### D-030 两个实现层的真坑（3.x 落地时才暴露）

1. **`OAuth2PasswordBearer` 返回的是原始 token 字符串，不是 `HTTPAuthorizationCredentials`**（后者是 `HTTPBearer` 的返回类型）。
   我按后者写了 `credentials.credentials`，7 个用例同时变红：`AttributeError: 'str' object has no attribute 'credentials'` ——
   后果是把本该 401 的请求变成 500。**测试一次就把类型假设的错误抓住了**，改法是直接 `decode_access_token(token, settings)`。
2. **argon2id 的实测数字**（默认参数 `time_cost=3` / `memory_cost=64MiB` / `parallelism=4`）：摘要 **97 字符**、单次哈希 **56ms**、校验 **55ms**。
   → 摘要长度落进 `VARCHAR(255)` 余量充足（ADR-0002 的"不改 DDL"成立）；
   → 56ms 是 CPU 密集操作，服务层一律 `asyncio.to_thread` 丢线程池，不在事件循环里算。
3. **每请求只有一个 DB session**：`get_db_session` 同时被 `get_current_user` 与端点依赖，FastAPI 的依赖缓存（`use_cache` 默认开）保证它只被解析一次。
   这是"注册返回 201 后库里立刻查得到"的前提——否则会出现两个 session、两个事务，提交时序会变得难以推理。

### D-031 端到端验收的时机陷阱：别在容器刚重建完就发写请求

- **现象**：`docker compose up -d --build` 返回后立刻跑 E2E，11 项全 PASS；但随后查库发现**那一轮注册的账号（id=1）根本不在库里**——而同一个脚本再跑一遍，账号（id=3）稳定落库；单独发一次注册（id=2）也稳定落库。
- **归因**：只有那一轮压在**容器替换窗口**上（旧 api 容器排空/终止时期）。我不掌握更细的因果关系，**就不编造更具体的成因**；能确定的是这个窗口不可信。
  （顺带排除掉了"提交根本没生效"这个更可怕的可能：`session_scope` 的提交路径本身是正确的，id=2 / id=3 都是磁盘上的真实行。）
- **两条可复用规则**：
  1. **写操作的端到端验收要等服务稳定后再跑**，不要紧接在 `up -d --build` 之后；
  2. **"成功"必须以查库为准，不能只看接口回了 201** —— 本次正是靠 `SELECT ... FROM users` 才发现缺失，接口侧当时 11/11 全绿，完全看不出问题。
- **善后**：残留的 `probe_*` / `e2e_*` 测试行已用 `DELETE` 清掉并复核 `users` 计数为 0（开发库不留测试数据）。

### D-032 两个"规格未规定项"定案 + 本组代码审查结论（2026-09-12）

**开发者拍板（本人作答，未代答）**

| 未规定项 | 结论 | 落地 |
| --- | --- | --- |
| 用户名大小写 | **区分大小写**（`alice` ≠ `Alice`） | 保持现状、零行为改动；已写进 `user-auth` 规格 Requirement + 新增「用户名区分大小写」场景 + 测试 `test_register_is_case_sensitive_on_username` |
| 密码长度上限 | **加 128 字符上限** | 新增配置 `PASSWORD_MAX_LENGTH=128`（`.env.example` 同步）；`schemas/auth.py` 校验并点名"长度不超过 128 位"；`test_config` 校验默认值与可覆盖；`test_auth_api` 加超限用例与**恰好 128 字符必须通过**的边界用例 |
| 第 3 组提交方式 | 先 review 再提交 | 见下 |

**为什么上限进配置、而 argon2 的 `time_cost` / `memory_cost` 不进**（避免与 ADR-0002 D2 读起来自相矛盾）：
前者是**输入护栏**——挡畸形超长输入白耗算力，不改变任何安全强度；后者是**抗爆破旋钮**——做成环境变量只会给人调小的机会。
性质不同，所以一个进 `Settings`，一个留代码常量。

**代码审查结论（两轴并行子代理，基线 `d9a1cb2` → 工作区；改动未提交，故给的是工作区 diff + 新增文件）**

- **Standards 轴**：**无硬违规**。4 条判断题，其中 1 条已修：
  - ✅ 已修：`tools/verify_auth_e2e.py` 硬编码端口 `8080` 与有效期 `86400` → 改为从仓库 `.env` 读 `NGINX_HOST_PORT` / `TOKEN_EXPIRE_MINUTES`。
    （否则开发者一改 `.env`，这个脚本就会假失败——正是"绿灯不可信"的反面教材）
  - 接受不改：`schemas/auth.py` 的 `username max_length=64` 是对齐 DDL 的 `VARCHAR(64)`，不是业务旋钮；做成配置反而可能配出超过列宽的值
  - 接受不改：`_DUMMY_PASSWORD` 是刻意公开的常量，不是密钥
- **Spec 轴**：整体忠实（登录不区分原因、凭证失效/过期/伪造/已删一律 401、注册响应只有 `{id, username}`、强度规则与点名、用户名唯一、区分大小写，均达标）。
  3 项"规格未覆盖"**记录在案、未擅自改规格**，等开发者定：
  1. `3.3` 真正的越权**写**操作要等 4.1 / 5.2 有接口后才能端到端验（tasks.md 已注明 defer，不是缺陷）
  2. 用户名**两端去空白归一化**与**长度上限 64 / 非空**：规格未写，是实现在输入层加的规范化
  3. `GET /api/auth/me`：规格未显式要求，作为 3.3 的受保护接口样本存在
- **按审查意见加强的测试**：新增 `test_login_does_the_same_hash_work_for_an_unknown_user` —— 用 monkeypatch 计数证明
  "用户不存在时也**恰好跑一次**校验、入参为 `None`"。比原来只断言"两条路径耗时都 >10ms"更硬：耗时受机器负载影响，
  这是在断言**机制**而不是旁证。

### D-033 镜像构建每次都全量重下依赖（10 分钟起）—— 待优化，未擅自改

- **现象**：`docker compose up -d --build` 每次都要 10 分钟以上。构建日志显示时间几乎全花在容器内 `pip install` 的
  `Downloading <wheel>` 上（实测单个 wheel 5~25 秒）。
- **根因（已核实）**：`backend/Dockerfile` 里设了 `PIP_NO_CACHE_DIR=1`，且 `RUN python -m pip install .` 没有挂 BuildKit
  缓存挂载 → **构建层缓存一旦失效（例如 `app/` 或 `pyproject.toml` 变了），所有依赖就重新下载一遍**。
  改代码是本项目的日常动作，所以这个代价每轮都要付。
- **建议修法（未实施，等你点头）**：给该 RUN 加缓存挂载，并去掉 `PIP_NO_CACHE_DIR`：
  ```dockerfile
  RUN --mount=type=cache,target=/root/.cache/pip \
      python -m pip install --upgrade pip && python -m pip install .
  ```
  （`PIP_NO_CACHE_DIR=1` 的初衷是"让镜像小一点"，但实际上 pip 的下载缓存在**构建期**、不进镜像层，
  去掉它不会让镜像变大。）
- **为什么不顺手改**：这属构建基础设施变更，且每次验证都要再等一次 10 分钟重建；本组正处在"提交前"的收口阶段，
  不宜同时动 Dockerfile 与业务代码。建议单独一项做（可放在 W5 收尾或第 5 组需要频繁重建上传接口时）。
