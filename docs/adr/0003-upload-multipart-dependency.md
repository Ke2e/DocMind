# ADR-0003：上传接口的传输形态与 `python-multipart` 依赖

- **状态**：**Approved**（开发者 2026-09-13 在开工问答中批复"装 python-multipart（推荐）"）
- **日期**：2026-09-13
- **决策来源**：`openspec/changes/add-doc-ingest-pipeline/tasks.md` 5.1（上传接口）；`AGENTS.md` §3「新增依赖 = 架构级决策，先写 ADR 等批」与 §6 停机点第 3 条
- **影响范围**：`backend/pyproject.toml` 依赖清单 → `backend/Dockerfile` 镜像内容；`POST /api/documents` 的请求形状（以及 5.2 / 5.3 的验收脚本、未来的 React 上传组件）

---

## 背景

### 这次决策为什么不得不做

第 5 组开工前，交接材料（`docs/HANDOFF.md` 第二节）对本组的判断是"**预期零新依赖，不涉停机点**"。
开工时按规矩先做了一次机器核查，这个判断被证伪：

| 位置 | 探测命令 | 结果 |
| --- | --- | --- |
| `backend/.venv` | `pip list \| grep -i multipart` | **0 命中** |
| `docmind-api` 容器 | `python -c "import importlib.util as u; print(bool(u.find_spec('multipart')))"` | **`False`** |
| `backend/pyproject.toml` | `grep multipart` | **无**（且它不是 `fastapi` / `uvicorn[standard]` 的传递依赖） |
| 全仓库 | `grep -rn "multipart\|UploadFile\|form-data"`（排除 `.venv`） | 只有 pip vendor 内的无关命中；**规格 / 提案 / tasks 均未规定上传的传输形态** |

而 FastAPI 的 `UploadFile` / `File()` / `Form()` **必须有 `python-multipart` 才可用**
（缺失时在路由注册期即抛 `RuntimeError: Form data requires "python-multipart" to be installed.`）。

结论：5.1 的"请求形态"是一个**尚未被任何文档决定的开放项**，且其中一种走法要新增依赖
→ 按 `AGENTS.md` §3/§6 属停机点，不得自行选型，故出本 ADR 等批。

### 已经就位、本次不再重议的约束

| 约束 | 出处 | 对决策的影响 |
| --- | --- | --- |
| 单文件上限 50MB；支持 PDF / DOCX / MD / TXT；提交阶段即拒绝超限与不支持类型，且**不产生半成品文档记录** | `specs/001-doc-ingest-pipeline/spec.md` FR-015 / SC-009；`app/core/config.py` 的 `MAX_UPLOAD_MB` / `ALLOWED_EXTENSIONS` | 传输层必须支持**流式**读入（不能把整份文件先读进内存），且大小判定必须发生在写库之前 |
| 提交后立即返回受理结果与文档标识，**MUST NOT 让请求等待解析完成** | 同上 spec「提交文档并立即受理」；SC-001（10MB ≤ 2 秒） | 请求形状本身不承担处理，只承担"收下 + 落盘 + 落库 + 投递" |
| 文件落挂载卷，api 与 worker 共享；不引入对象存储 | `design.md` D9；`docker-compose.yml` 的 `uploads:/data/uploads` | 落盘方式是本地卷写入，与传输形态无关 |
| 反向代理已有 `client_max_body_size 60m`（略大于 50MB 上限） | `docker/nginx.conf` | nginx 已是字节级外层闸门；应用层只需做语义级判定，**本 ADR 不改 nginx** |
| 依赖只有一条声明路径：`backend/pyproject.toml` 的 `dependencies`（无 `requirements.txt` / lockfile），镜像走 `pip install .` | `AGENTS.md` §3；`docs/HANDOFF.md` 第一节 | 若采纳新依赖，必须进 `dependencies`（不是 dev extras），只装本地 venv 无效 |

### 与宪法两条原则的合规声明（`AGENTS.md` §1 强制）

- **原则 I（原生实现保护清单）**：保护清单是分块 / 双路召回 / RRF / 重排 / 上下文压缩 / mini-agent 工具调用循环 / 引用对齐 / 语义缓存。
  **multipart 报文解析不在其中**，它既不是 RAG 链也不是检索组件；用 `python-multipart` 不构成"用现成链替代手写核心算法"，无违规。
- **原则 II（技术栈锁定）**：技术栈清单（Python 3.12 / FastAPI / Pydantic v2 / SQLAlchemy 2.0 async / Alembic / PG16 / Milvus / Celery+Redis / LangGraph；前端 React 18 + TS + Vite）
  **未列 multipart 解析库**，故本次属"技术栈新增"，必须经本 ADR 批准后落地 —— 这正是本 ADR 存在的原因。

---

## 决策

**采纳方案 A：使用 `python-multipart`，上传接口走标准的 `multipart/form-data`。**

- `POST /api/documents`，`Content-Type: multipart/form-data`，两个部分：
  - `file`：文件本体（`UploadFile`），流式读取
  - `kb_id`：归属知识库 id（`Form`，必填 —— 对应 FR-011"每份文档必须且只能归属一个知识库"）
- `backend/pyproject.toml` 的 `dependencies` 新增 `python-multipart>=0.0.9`
- 版本下界取 `0.0.9`：FastAPI 0.141 对 multipart 解析有安全修复要求（CVE-2024-53981 的分段拒绝服务），下界落在修复版之后

### 备选方案与被否理由

| 方案 | 做法 | 为什么否掉 |
| --- | --- | --- |
| **B. 原始字节流（零依赖）** | `POST /api/documents?kb_id=..&filename=..`，body 直接是文件字节（`application/octet-stream`），后端边读边数大小 | 技术上完全可行且零依赖，**但**：非标准形态、Swagger UI 没有文件选择框（后续手测要自己拼 body）、前端必须 `fetch(url,{body:file})` 并手设 header；更要紧的是**它把"文件名"从报文元数据降级成了查询参数** —— 一旦 002 起要加"同一请求附带的表单字段"（如自定义 metadata、分块参数覆盖），这个形状必须推倒重来。本次新增依赖的代价只有 ~30KB 纯 Python 解析器，换标准形态划算 |
| **C. 手写 multipart 解析（零依赖）** | 自己解析 boundary / part 头 / CRLF / 转义 | 零依赖且保持标准形态，但 multipart 解析是公认易错脏活（boundary 折行、`Content-Disposition` 的 filename* 编码、分块上传），**且它不在保护清单里** —— 为省一个 30KB 依赖自造轮子，属典型的"投机性泛化"（`AGENTS.md` §4 karpathy-guidelines）。否 |

### 连带定下、写进本 ADR 以免后人反复的三个实现取舍

| 取舍 | 结论 | 理由 |
| --- | --- | --- |
| 提交成功的状态码 | **201 Created**（不是 202） | 接口确实**创建了一个资源**（`documents` 行 + `processing_tasks` 行），与 4.1 建知识库的 201 保持同一口径；202 会暗示"这是一个与资源无关的异步作业"，而本项目里文档标识就是资源的标识 |
| 不支持类型的拒绝码 | **415 `unsupported_media_type`** | 1.6 的错误契约里早已登记该码（`app/core/errors.py`），此前无接口用到；语义精确，比笼统的 422 更能让前端分流提示 |
| 超限的拒绝码 | **413 `payload_too_large`** | 同上，契约里已有该码；且与 nginx 外层闸门（60m）同码，前端只需处理一种 |

> 别名说明：若 10.1 的端到端脚本要传"超出 50MB 但 ≤ 60MB"的请求，应用层回 413；
> 传"超过 60MB"的请求，nginx 会先回 413（HTML 体，非本项目错误契约）—— 这是外层闸门的既定行为，不在本期范围内改。

---

## 验证证据（命令与输出）

```bash
# 1) 决策前提：python-multipart 确实缺席（开工前实测）
cd backend && .venv/Scripts/python.exe -m pip list | grep -i multipart
# → （0 行）
docker exec docmind-api python -c "import importlib.util as u; print(bool(u.find_spec('multipart')))"
# → False

# 2) 决策前提：全仓库没有任何"上传传输形态"的既有规定
grep -rn -i -E "multipart|UploadFile|form-?data|application/octet-stream" \
  --include=*.md --include=*.py --include=*.toml --include=*.yml . | grep -v '\.venv'
# → 仅命中 .venv 内 pip vendor 的无关文件（已在仓库外剔除）

# 3) 落地后复核：依赖进了 venv、也进了镜像
cd backend && .venv/Scripts/python.exe -m pip show python-multipart | head -2
docker exec docmind-api python -c "import multipart, importlib.metadata as m; print(m.version('python-multipart'))"
# → 两者都应打印版本号（实测输出见 docs/progress.md 第 5 组「证据」一节）
```

---

## 影响与后续

- **镜像**：多一个纯 Python 包，无 C 扩展、无编译步骤；构建缓存命中与否看日志计数（`docs/findings.md` D-034 的判据），不看耗时。
- **未来扩展**：002 起若上传需要附带表单元数据（分块参数覆盖、标签等），标准 multipart 可以原地加字段，不必改接口形状 —— 这正是选 A 而非 B 的主要收益。
- **安全边界**：客户端提供的文件名**只用于展示与扩展名判定**（`documents.original_filename`），落盘文件名由服务端 `uuid4().hex` 生成，不参与路径拼接（防路径穿越）。这条是 5.1 的实现约束，随代码落地并在测试中锁住。
