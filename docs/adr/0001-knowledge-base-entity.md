# ADR-0001：引入 knowledge_bases 实体（DDL 变更）

- **状态**：**Approved**（开发者 2026-09-12 批准，随 W5 落地）
- **日期**：2026-09-12
- **决策来源**：`specs/001-doc-ingest-pipeline` 澄清 Q3 → 选项 B
- **影响范围**：PostgreSQL DDL、文档上传链路、检索过滤条件、002 的 Milvus collection schema

## 背景

`docs/PROJECT_CONTEXT.md` 第 3 节架构图与第 4 节目录结构里都出现了"知识库管理"，但第 5.1 节的 DDL 中 `documents` 只挂 `user_id`，没有知识库维度——即"知识库"在产品叙事里存在，在数据模型里不存在。

W5 澄清时确认走选项 B：一个用户可建多个知识库，文档归属知识库，查询与检索按"用户 + 知识库"双重过滤。

## 决策

1. 新增表：

   ```sql
   CREATE TABLE knowledge_bases (
     id BIGSERIAL PRIMARY KEY,
     user_id BIGINT REFERENCES users(id),
     name VARCHAR(128) NOT NULL,
     description TEXT,
     created_at TIMESTAMPTZ DEFAULT now()
   );
   CREATE UNIQUE INDEX uq_kb_user_name ON knowledge_bases(user_id, name);
   ```

2. `documents` 增加 `kb_id BIGINT NOT NULL REFERENCES knowledge_bases(id)`，并建 `idx_documents_kb ON documents(kb_id)`。

3. **不做级联删除**：删除仍含文档（含处理中文档）的知识库被拒绝，返回未清空文档数量。理由：后台任务正在写入时级联删除会产生竞态与孤儿片段。

4. 同名知识库在同一用户下唯一（唯一索引兜底，接口层给出可读提示）。

5. 所有知识库/文档查询必须带 `user_id` 过滤（与保护清单一致），按知识库筛选时再叠加 `kb_id`。

## 对 002（向量化）的前置约束

Q2 结论为"001 不落向量数据"，因此本期不创建 Milvus collection。但 002 建 `doc_chunks` collection 时**必须包含 `kb_id INT64` 字段**，否则检索无法在向量层做知识库过滤（只能先查 PG 再回过滤，性能与实现复杂度都会变差）。此项记入 002 的规格输入，属于"Milvus collection schema"范畴——按禁改清单需走提案（本 ADR 即为该提案的前置依据）。

## 被否方案

| 方案 | 否决理由 |
|---|---|
| A：不加表，`documents` 直接挂 `user_id`，"知识库"= 用户全部文档 | 与产品形态（多知识库管理页）不符；后续若要加库，需改 DDL 且所有检索条件返工 |
| C：引入 workspace / 团队空间，支持多人共享知识库 | 需额外建模成员、角色、共享规则，工作量显著超出 W5；与"面试讲 RAG 优化"的主线目标不匹配 |

## 批准后要做的动作

1. 在 `specs/001-doc-ingest-pipeline/spec.md` 的 Dependencies 中把该项标记为"已批准"
2. 生成 Alembic 迁移（**新增文件，不改已有版本**）
3. 更新 `docker-compose.yml` 中 PG 初始化方式（如使用初始化 SQL 则同步）
4. 002 规格起草时引用本 ADR 的"对 002 的前置约束"一节
