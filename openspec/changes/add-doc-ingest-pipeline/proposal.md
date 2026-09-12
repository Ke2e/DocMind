## Why

DocMind 目前只有规划，没有任何内容进得来。平台的全部下游能力（向量化、混合检索、Agentic RAG、引用溯源）都建立在"文档已被解析成可检索片段"这一前提之上；没有这条地基，后面所有周次的验收都无法启动。

同时，数据归属模型必须在这一步就定死——账号、知识库、文档三者的归属关系一旦后面再改，检索过滤条件与前端都要返工。因此 W5 的目标是把"账号 → 知识库 → 文档进库"做成第一个可端到端验收的增量。

## What Changes

- 新增账号体系：注册、登录、登录态校验；所有内容接口需要有效登录态
- 新增知识库：用户可创建、列出、重命名、删除自己的知识库；文档必须且只能归属一个知识库
- 新增文档上传：支持 PDF / DOCX / MD / TXT，单文件上限 50MB；提交即受理并返回文档标识，不等解析完成
- 新增异步处理管线：解析 → 清洗 → 分块在后台执行；文档状态机为 uploaded → parsing → chunking → ready | failed（保留 embedding 阶段位但不启用）
- 新增进度查询：按文档返回当前阶段与已完成阶段
- 新增失败处理：自动重试 2 次（指数退避），失败后可手动重试至多 3 次；失败原因以可读文本回写
- 新增删除语义：删除文档级联清除其片段与处理记录；删除仍含文档的知识库被拒绝
- **BREAKING**（对既有 DDL 而言）：新增 `knowledge_bases` 表，`documents` 增加 `kb_id NOT NULL` 外键——见 `docs/adr/0001-knowledge-base-entity.md`（已批准）

## Capabilities

### New Capabilities

- `user-auth`: 账号注册、登录与登录态校验，为内容接口提供身份与数据归属维度
- `knowledge-base`: 知识库的创建、列出、重命名、删除，以及文档归属知识库的约束
- `document-ingest`: 文档上传、后台解析/清洗/分块管线、处理状态与进度查询、失败重试、删除级联

### Modified Capabilities

（无。项目尚无任何已部署规格，这是首个 change。）

## Impact

- **数据库**：新增 `knowledge_bases`（id / user_id / name / description / created_at，用户名下唯一）；`documents` 增 `kb_id NOT NULL` 与索引；`chunks` 沿用既有设计。迁移为新增文件，不改动已有版本
- **接口**：新增 `/api/auth/register|login`、`/api/knowledge-bases`（CRUD）、`/api/documents`（上传 / 列表 / 详情 / 进度 / 重试 / 删除）
- **运行环境**：需要容器化全家桶（api / worker / beat / pg / redis / nginx）健康启动；Milvus 相关容器本期只起不用
- **依赖**：文档解析与计数（pypdf / python-docx / markdown / tiktoken）均在既定技术栈内，无新增依赖
- **对 002 的约束**：Milvus `doc_chunks` collection 建表时必须包含 `kb_id` 字段，否则向量层无法做知识库过滤（ADR-0001）
- **规格基线**：`specs/001-doc-ingest-pipeline/spec.md`（W5 冻结基线，本 change 是其上的正式提案）
