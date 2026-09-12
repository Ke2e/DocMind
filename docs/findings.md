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
