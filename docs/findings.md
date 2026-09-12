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
