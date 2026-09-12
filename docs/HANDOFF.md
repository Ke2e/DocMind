# DocMind 开发交接文档

**交接时间**：2026-09-12
**交接范围**：W5（第 1 周）任务 0 全部完成，任务 1 待开工
**给下一个会话**：读完本文 + `AGENTS.md` 即可接手，不需要回溯聊天记录

---

## 一、当前状态（一句话）

W5 的规格、提案、治理文件、环境变量、git 仓库、验收语料都已就位；
**卡在停机点 2，等开发者确认周计划后开始写代码**。

---

## 二、下一步从哪开始

1. **确认周计划**：`openspec/changes/add-doc-ingest-pipeline/tasks.md`（10 组 / 32 项，每项带验证方式）
   - 开发者可能有增删 → 改完后再动工
2. 确认后执行 `/opsx:apply`（或直接按 1.1 → 1.2 … 顺序实施）
3. 首项开工内容是 **1.1 初始化 git 已完成，从 1.2 开始**：
   - 1.2 搭 `backend/` 分层骨架
   - 1.3 Docker Compose（Milvus 走可选 profile，默认不启动）
   - 1.4 配置系统（`.env` / `.env.example` 已就位，按其中分组实现加载与校验）

> ⚠️ 1.1（git 初始化）在 2026-09-12 已由交接方完成，可直接勾掉：
> `git init -b main` + 首次提交 `d34b36b`，43 个文件入库，`.env` 等已按 `.gitignore` 排除。

---

## 三、本机环境速查（踩过的坑，务必先看）

| 坑 | 现象 | 对策 |
| --- | --- | --- |
| **Bash 工具 PATH 会被清空** | `ls`/`grep`/`dirname` 等 coreutils 报 `command not found`，npm shim 解析失败（曾误判 openspec 未安装） | 每条命令开头显式设置 PATH（见下） |
| `git.exe` 不在 PortableGit/bin | `git: command not found` | 需把 `.../PortableGit/versions/1.2.0/cmd` 加进 PATH |
| 沙箱只允许写工作区内 | 往 `C:\Users\ASUS\.workbuddy\...` 建 venv 静默失败（exit 0 但无目录） | 依赖装进项目内 `.venv/`（已在 .gitignore） |
| PowerShell 工具不回显 stdout | 命令 exit 0 却看不到输出 | 改用 Bash；必须用 PS 时改看退出码 + 之后用 Glob/Read 核验 |

**统一 PATH 前缀（建议每条 Bash 命令都用）：**

```bash
export PATH="/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/cmd:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:/c/Users/ASUS/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/d/nvm/nodejs:/usr/bin:/bin"
```

**已就绪的工具**

- `openspec` v1.11.0（`D:\nvm\nodejs` → nvm v24.9.0）
- `specify`（spec-kit）v1.0.1 —— 仅历史用途，不再驱动开发
- git 2.55.0，全局身份 `Asize <3238075590@qq.com>`
- `.venv/`（Python 3.13.14）+ reportlab / python-docx / pillow / pypdf（**只用于生成验收语料**，与后端运行时依赖无关）

---

## 四、已冻结的决策（不要再重新讨论）

| 项 | 结论 | 权威出处 |
| --- | --- | --- |
| 规格流程 | **OpenSpec 单主线**（`changes/` → apply → archive）；spec-kit 仅作 W5 启动文档，`/speckit.*` 已弃用 | `AGENTS.md` §1、`.specify/memory/constitution.md` 原则 V |
| 本增量范围 | 到 W5 为止：解析→清洗→分块→状态可查→失败重试；**向量化与问答留 002** | `specs/001-doc-ingest-pipeline/spec.md` |
| 数据模型 | 新增 `knowledge_bases` + `documents.kb_id`，查询按"用户 + 知识库"双过滤 | `docs/adr/0001-knowledge-base-entity.md`（已批准） |
| 支持格式 | PDF / DOCX / MD / TXT，单文件 ≤ 50MB，无 OCR | 同上 spec FR-015 / SC-009 |
| 失败重试 | 自动 2 次（指数退避）+ 手动至多 3 次，失败原因可读回写 | 同上 spec FR-008/009 |
| 删除语义 | 文档删除级联清片段；**非空知识库拒删**（防与后台任务竞态） | ADR-0001 |
| 目录布局 | 代码与规格直接放仓库根，不再嵌套 `docmind/` 层 | `AGENTS.md` §7 |
| Milvus | compose 中列为可选 profile，**本期默认不启动** | `design.md` D1/D9 与风险节 |
| 002 前置约束 | 建 `doc_chunks` collection 时**必须带 `kb_id` 字段** | ADR-0001 末节 |

澄清问答原文见 `specs/001-doc-ingest-pipeline/clarify-answers.md`；规格质量清单 16/16 通过。

---

## 五、工件地图

```
AGENTS.md                               AI 运行时规则（会话启动必读）
.env / .env.example                     真实密钥 / 可提交样例（.env 已被忽略）
.gitignore / .gitattributes             忽略规则（含 .env、.venv、.codebuddy、.workbuddy、fixtures/acceptance）
openspec 产物 ↓
openspec/config.yaml                     schema: spec-driven，语言 zh-CN
openspec/changes/add-doc-ingest-pipeline/
    ├── proposal.md                      Why / What Changes / Capabilities / Impact（DDL 变更标 BREAKING）
    ├── specs/user-auth/spec.md          账号注册、登录、数据归属（ADDED Requirements + 场景）
    ├── specs/knowledge-base/spec.md     知识库 CRUD、归属约束、非空拒删
    ├── specs/document-ingest/spec.md    上传受理、四格式与 50MB、异步管线、状态与进度、重试、删除级联
    ├── design.md                        D1–D9 技术决策 + 风险 + 迁移计划 + 开放问题
    └── tasks.md                         10 组 / 32 项实施清单（每项含验证方式）
.specify/memory/constitution.md          项目宪法 v1.1.0（保护清单 / 技术栈 / 停机点）
specs/001-doc-ingest-pipeline/spec.md    W5 规格基线（19 FR / 9 SC / 5 US），冻结
docs/PROJECT_CONTEXT.md                  项目简报（已修正过期的模型名）
docs/task_plan.md                        周级计划与当前状态
docs/findings.md                         决策沉淀 D-001 ~ D-013
docs/progress.md                         进度流水（含验收证据位）
docs/notes.md                            teach 讲解笔记骨架（W5 起逐周填）
docs/adr/0001-knowledge-base-entity.md   DDL 变更决策（Approved）
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
2. **`.codebuddy/` 与 `.workbuddy/` 未入库**（含会话数据风险，且可由 `openspec update` 重建）。
   换机器时需重跑 `openspec init --tools codebuddy --language zh-CN`。
3. **`.specify/` 入库但已停用**，保留作历史与宪法来源；新会话不要被它误导回 spec-kit 流程。
4. 环境准备（Docker Desktop、`.env` 里数据库/缓存/签名密钥）由开发者本地完成，
   模型密钥 W5 期间可留空（只告警不阻断）。
5. 未验证项：`RERANK_BASE_URL` 的 `parameters.top_n` 语义（返回条数）已实测有效，
   但 `top_n` 与 `return_documents` 之外的参数（如 `max_chunks_per_doc`）未测，W7 做重排时先小样验证。
