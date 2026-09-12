## 1. 版本管理与运行环境

- [x] 1.1 初始化 git 仓库与 `.gitignore`（排除 `.env`、`.codebuddy/`），验证：`git status` 中不出现真实 `.env`，首次提交成功
  - 完成证据（2026-09-12）：`git init -b main` + 首次提交 `d34b36b`（43 文件）；`git check-ignore -v .env` 命中；`git log --oneline` 3 次提交，`git status --short` 为空
- [x] 1.2 按 OneHub 已验证分层搭 `backend/` 骨架（`app/core` `app/api` `app/models` `app/schemas` `app/services` `app/workers`）与依赖清单，验证：本地能起空应用，`GET /health/live` 返回 200（**不依赖任何外部服务**），`GET /health/ready` 单独反映 PostgreSQL / Redis 连通性
  - 完成证据（2026-09-12）：`backend/.venv`（Python 3.12.3）+ 依赖装齐；`uvicorn app.main:app --port 8001` 启动日志 `Application startup complete.`；`/health/live` → 200 `{"status":"ok"}`；pg/redis 未起时 `/health/ready` → 503 并逐个报不可用，容器环境就位后 → 200 `{"status":"ok","checks":{"database":null,"redis":null}}`
- [x] 1.3 编写 Docker Compose（api / worker / beat / pg / redis / nginx，Milvus 系列列为可选 profile），验证：`docker compose up -d` 后全部容器 healthy，且默认不启动 Milvus 相关容器
  - **端口约束（本机实测冲突）**：宿主 8000 / 5432 / 6379 已被既有 OneHub 栈占用，9000-9001 / 9091 / 19530 被既有 Milvus 占用。故 compose 使用独立 `name: docmind`，宿主端口映射为 **pg 5433 / redis 6380 / nginx 8080**，api 容器内 8000 不对宿主暴露；Milvus profile 另取空闲端口
  - 完成证据（2026-09-12）：`docker compose ps` → api / worker / beat / pg / redis / nginx **6/6 healthy**；`docker compose config --services` 不含 Milvus，`--profile milvus` 才出现 milvus-etcd / minio / standalone；`docker ps -a --filter name=docmind-milvus` 计数 **0**；OneHub 栈三容器未受影响
  - 附带验证：经 nginx 访问 `/health/live` → 200、`/health/ready` → 200（pg + redis 均连通）；beat 心跳键 `docmind:beat:heartbeat` 存在（TTL 79s），worker 日志每 30s 消费一次 `beat_heartbeat` 任务 → 证明 beat → broker → worker → redis 整条链路连通
- [x] 1.4 配置系统，与已就位的 `.env` / `.env.example` 对齐（**单一模型网关**，三个用途共用一个 `BASE_URL` + `API_KEY`）：
  - 本期必需（缺失即启动失败）：`DATABASE_URL`、`REDIS_URL`、`SECRET_KEY`
  - 本期占位（W5 不参与数据流，缺失只告警不阻断）：`BASE_URL`、`API_KEY`、`GENERATIVE_MODEL`、`EMBEDDING_MODEL` + `EMBEDDING_DIM`、`RERANK_MODEL` + `RERANK_BASE_URL`
  - **业务参数外置清单**（全部进配置，代码中不得出现字面量；各任务"参数来自配置"以此为准）：
    - 存储：`UPLOAD_DIR`（api 与 worker 共享卷路径）、`MAX_UPLOAD_MB`（默认 50）、`ALLOWED_EXTENSIONS`（默认 pdf/docx/md/txt）
    - 分块（供 6.2）：`CHUNK_SIZE_TOKENS`（默认 512）、`CHUNK_OVERLAP_TOKENS`（默认 64）
    - 重试与补偿（供 8.1 / 8.2 / 8.3）：`AUTO_RETRY_MAX`（默认 2）、`MANUAL_RETRY_MAX`（默认 3）、`RETRY_BACKOFF_BASE_SECONDS`、`STUCK_TASK_THRESHOLD_SECONDS`、`BEAT_HEARTBEAT_INTERVAL_SECONDS`
    - 鉴权（供 3.1 / 3.2）：`PASSWORD_MIN_LENGTH`（默认 8）、`TOKEN_EXPIRE_MINUTES`、`JWT_ALGORITHM`
  - 需注意：重排不在 `/compatible-mode/v1` 下（实测 404），必须用 `RERANK_BASE_URL` 指向 DashScope 原生路径 `/api/v1/services/rerank/text-rerank/text-rerank`，请求体为 `{model, input:{query,documents}, parameters:{top_n,return_documents}}`，响应取 `output.results[].relevance_score`
  - 完成证据（2026-09-12）：`pytest -q` → **11 passed**；进程级验证「不读 `.env` 且无环境变量」→ `ConfigError -> 配置缺失，应用无法启动：DATABASE_URL、REDIS_URL、SECRET_KEY（读取自 …\.env 或环境变量；请参考 .env.example 补齐）`；只缺占位项时启动成功并打印 `模型网关配置未就位` 告警（`tests/test_config.py`）；`test_no_hardcoded_model_or_endpoint_in_app_source` 扫描 `backend/app/**/*.py` 确认无模型名 / 服务商地址字面量
- [x] 1.5 测试脚手架：pytest + pytest-asyncio + httpx `AsyncClient`，`conftest` 提供测试库 schema 建/销毁、事件循环、应用实例、双账号 fixture，验证：`pytest` 能跑通一个最小用例；测试前后测试库无残留表；测试不依赖已启动的 worker（可在无 Celery 下运行接口测试）
  - 落地节奏：脚手架本体（配置隔离 / 客户端 / 测试库 schema 建·销毁 fixture）随本项交付；**双账号 fixture 依赖 `users` 模型，随 3.x 补齐**
  - 完成证据（2026-09-12）：`backend/tests/conftest.py` 在导入应用前用环境变量顶掉 `.env`（测试永不连开发库）；`client` / `raw_client`（容忍应用内异常，用于验 500 响应体）双客户端就位；`db_schema` fixture 对 `Base.metadata` 先 drop 后 create、用例结束再 drop，库不可达时 **skip 而非假通过**；`pytest -q` 11 passed 且全程未启动 Celery
- [x] 1.6 统一错误响应契约：定义错误响应体（机器可读 `code` + 面向用户的可读 `message`，可选 `detail`）与全局异常处理器，验证：触发未捕获异常时响应体结构符合契约且**不含堆栈、模块路径等内部细节**（7.2 的前提）；404 / 422 等默认错误同样归一
  - 完成证据（2026-09-12）：`backend/app/core/errors.py` 定义 `ErrorCode` 枚举、`AppError` 及子类与四类全局处理器；`tests/test_error_contract.py` 覆盖 404（框架默认）/ 422（参数校验）/ 500（未捕获异常）/ 业务异常四条路径，均返回 `{code, message, detail?}`；500 路径响应体中 `Traceback`、`site-packages`、SQL 片段等标记词检查全部不命中

## 2. 数据模型与迁移（ADR-0001）

- [ ] 2.1 定义 SQLAlchemy 模型：本仓库当前无任何表，需**新建全部 5 张表**——`users`、`knowledge_bases`（ADR-0001）、`documents`（含 `kb_id NOT NULL` FK）、`chunks`（加 `(document_id, chunk_index)` 唯一约束）、处理任务表；字段清单以 `specs/001-doc-ingest-pipeline/spec.md` Key Entities（FR-018 含原始文件名 / 类型 / 字节大小 / 状态 / 失败原因 / 片段数量 / 归属知识库 / 创建时间）为准
  - 说明：ADR-0001 所称 "BREAKING" 是相对 001 设计稿而言；对本仓库而言是**全新建表**，不存在"已有 users / documents 再增字段"
  - 验证：模型可导入无循环依赖，`metadata` 打印出的表与字段符合 ADR-0001 描述与 Key Entities 清单
- [ ] 2.2 生成 Alembic 迁移（新增文件，不改历史版本）并在干净库上验证 upgrade / downgrade，验证：upgrade 后存在 `uq_kb_user_name` 与 `idx_documents_kb`，downgrade 后回到初始结构
  - 干净库说明：本机无本地 PostgreSQL，干净库取 compose 起的 pg 实例中独立创建的 `docmind_test` 库

## 3. 账号体系

- [ ] 3.1 注册接口（密码以不可还原形式存储、用户名唯一、强度校验），验证：接口测试覆盖成功 / 用户名重复 / 弱密码三种情况
  - 强度规则（开发者 2026-09-12 定）：长度 ≥ `PASSWORD_MIN_LENGTH`（默认 8）**且同时包含字母与数字**；拒绝时说明具体不满足项
- [ ] 3.2 登录与凭证签发（带有效期，有效期来自 `TOKEN_EXPIRE_MINUTES`），验证：正确凭证可换取登录凭证；错误凭证被拒且响应不区分"用户不存在"与"密码错误"
- [ ] 3.3 鉴权依赖组件：身份只由凭证推导，忽略请求体中的用户标识，验证：无凭证与伪造凭证访问内容接口均返回拒绝；请求体携带他人用户标识不影响归属

## 4. 知识库

- [ ] 4.1 创建 / 列表 / 重命名接口，验证：重名、空名、超长名被拒；**列表条目包含该知识库当前文档数量**（knowledge-base spec「列表包含文档数量」场景）；双账号交叉测试下列表只含自己的知识库；**重命名他人知识库被拒且数据不变**
- [ ] 4.2 删除知识库（非空拒删并返回未清空数量），验证：空库删除成功且从列表消失；非空库返回拒绝并给出文档数量

## 5. 文档上传与受理

- [ ] 5.1 上传接口：类型白名单（PDF / DOCX / MD / TXT）、单文件 `MAX_UPLOAD_MB` 上限、落盘到共享卷、写入 `uploaded` 记录、投递处理任务后立即返回，验证：10MB PDF 提交在 2 秒内返回受理结果且期间服务仍响应其他请求（SC-001，在 compose 环境中实测，排除首次冷启动）；超限与不支持类型在提交阶段被拒且不产生文档记录
- [ ] 5.2 文档归属约束（`kb_id` 必填 + 属主校验；原 4.3，因依赖上传接口而移入本组），验证：未指定知识库的提交被拒；向他人知识库提交被拒且不产生文档记录
- [ ] 5.3 任务投递与并发保护（分布式锁），验证：并发提交同一文档两次，只产生一条处理记录
- [ ] 5.4 片段反查接口（FR-005「可通过文档反查全部片段」），验证：返回该文档全部片段、按 `chunk_index` 升序；片段总数与文档 `chunk_count` 一致；越权访问他人文档的片段被拒
- [ ] 5.5 文档列表与详情接口，验证：响应包含归属知识库、状态与片段数量；双账号下只返回自己的文档；按知识库筛选时不跨库（SC-008）

## 6. 后台处理管线

- [ ] 6.1 **先写分块算法测试**（保护清单要求 TDD）：递归降级顺序、默认 512 / 64 参数、空文档、超长无标点段落、恰好等于粒度、表格密集，验证：测试文件先失败（实现未写），覆盖上述全部边界
- [ ] 6.2 原生实现分块器使测试转绿（不使用任何现成分割器），验证：全部测试通过；分块参数来自配置；**内容忠实性按三项校验**——(a) 覆盖性：原文的每个 token 位置至少被一个片段包含，无丢字；(b) 顺序性：片段按 `chunk_index` 升序拼接后与原文顺序一致；(c) 忠实性：每个片段都是原文的连续子串（忽略首尾空白归一化）。**注意**：默认 `CHUNK_OVERLAP_TOKENS=64` 使相邻片段共享边界文本，故不得以"拼接结果等于原文"作为判据
  - 参数生效范围另验：调整 `CHUNK_SIZE_TOKENS` / `CHUNK_OVERLAP_TOKENS` 后新处理的文档按新参数切分，已完成的历史文档不受影响（SC-007，与 6.5 幂等一起验）
- [ ] 6.3 解析适配层（PDF / DOCX / MD / TXT）与清洗（去重复页眉页脚噪声、统一空白与换行），验证：四种格式样例各自解析出非空文本；无文本层 PDF 抛出可被识别的错误类型
- [ ] 6.4 管线编排与状态迁移（`uploaded → parsing → chunking → ready`），状态迁移收敛到单一方法并拒绝非法迁移，验证：10MB PDF 全流程到达完成；`chunk_count` 与片段表实际行数一致
- [ ] 6.5 幂等写入（同一事务内先清后写 + 唯一约束兜底），验证：同一文档重复执行管线两次，片段数量与内容完全一致

## 7. 状态与进度

- [ ] 7.1 进度查询接口，验证：处理中返回当前阶段与**已完成阶段**且只向终态推进不回退；刚提交未被领取时返回"已接收"且不报错（SC-003）
- [ ] 7.2 失败信息可读化（错误分类映射），验证：构造解析失败，接口返回可读原因且响应中不含堆栈或内部实现细节（依赖 1.6 的错误契约）

## 8. 失败重试与中断补偿

- [ ] 8.1 自动重试（上限 `AUTO_RETRY_MAX`、指数退避）与失败原因回写，验证：提交损坏文件后，日志可见 2 次自动重试，最终状态为失败且带可读原因，全过程在 60 秒内（SC-005）
- [ ] 8.2 手动重试接口（上限 `MANUAL_RETRY_MAX`、重置状态、清理旧片段后重新投递），验证：重试后状态回到起点并走完状态机；达上限后返回明确提示且不重复执行
- [ ] 8.3 中断补偿扫描（beat 定时扫描长时间停留的中间态，阈值 `STUCK_TASK_THRESHOLD_SECONDS`），验证：手动终止执行进程造成中间态停留，扫描后该文档被重新调度或置为失败，不永久卡住；为便于复现，测试时把阈值调到极小值触发，不依赖真实超长等待

## 9. 删除与派生数据清理

- [ ] 9.1 删除文档（级联清除片段与处理记录 + 删除标记阻止写回），验证：删除后文档与其片段均不可查，且不再计入所属知识库的文档数量
- [ ] 9.2 处理中删除，验证：删除立即生效，随后不再产生该文档的新片段
- [ ] 9.3 越权删除防护，验证：以另一账号删除他人文档返回拒绝且数据完好

## 10. 周验收与留档

- [ ] 10.1 端到端验收脚本：4 种格式样例 + 10MB PDF + 损坏文件 + 无文本层扫描件 + 双账号越权用例，验证：脚本可一键运行并输出逐项结论
- [ ] 10.2 汇总周验收报告：把 SC-001 / 002 / 004 / 005 / 008 / 009 的实测数字整理成对照表写入 `docs/progress.md` 与验收报告，验证：每条 SC 都能追到可复现命令与输出
  - 调整说明（2026-09-12 开发者确认）：证据**逐组完成即回写** `docs/progress.md`（AGENTS.md §4 要求每个验收点留证据），10.2 只做汇总与 SC 对照，不承担"事后补证据"职责
- [ ] 10.3 补 W5 teach 笔记到 `docs/notes.md`（FastAPI 依赖注入、SQLAlchemy async、JWT、Celery 出栈与幂等），验证：笔记回答了"为什么这样设计"
  - 节奏建议：笔记随对应组（3 / 5 / 6 / 8 组）增量写入，不堆到最后
- [ ] 10.4 归档前自检，验证：`openspec validate add-doc-ingest-pipeline --strict` 通过；实现与 specs 的偏差已回写规格或记录为新的 change
