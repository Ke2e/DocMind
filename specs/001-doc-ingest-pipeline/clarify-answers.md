# /speckit.clarify 问答记录（001-doc-ingest-pipeline）

**提问时间**: 2026-09-10（清单见 git 历史中的 `clarify-pending.md`）
**作答时间**: 2026-09-12
**作答人**: 开发者 Asize（未代答）
**答案回填**: `spec.md` → `## Clarifications` + 各相关章节；项目级结论同步 constitution / AGENTS.md

| # | 问题 | 答案 | 落点 |
|---|------|------|------|
| Q1 | Spec 工作流主线用 spec-kit 还是 OpenSpec？ | **C — OpenSpec 单主线**，spec-kit 仅作为本次 W5 启动文档 | `spec.md`「规格归属」；`.specify/memory/constitution.md` 原则 V；`AGENTS.md` §1、§7 |
| Q2 | 001 覆盖到哪里为止？ | **A — 就到 W5**（分块完成即"完成"，向量化留 002） | `spec.md` Status / Assumptions / Out of Scope；状态机"向量化"位预留不启用 |
| Q3 | 要不要独立的"知识库"实体？ | **B — 要**，加 `knowledge_bases` 表，用户多库，按"用户 + 知识库"双过滤 | 新增 US2、FR-010~012/019、Key Entity、SC-008；`docs/adr/0001-knowledge-base-entity.md`（待批） |
| Q4 | 首版支持哪些格式、单文件上限？ | **A — PDF / DOCX / MD / TXT，50MB** | FR-015、SC-009、Edge Cases、Dependencies（验收语料） |
| Q5 | 解析失败的重试策略？ | **A — 自动重试 2 次（带退避）+ 手动重试** | FR-008/009、SC-005、Assumptions（手动上限 3 次） |

## 由答案导出的待办

1. **ADR-0001 待批准**（停机点 3）：`knowledge_bases` 新表 + `documents.kb_id` —— 批准后才生成 Alembic 迁移
2. **002 的前置约束**：`doc_chunks` collection 必须带 `kb_id` 字段（记入 002 规格输入）
3. **流程切换**：后续变更改走 OpenSpec `changes/` 提案流；spec-kit 的 plan/tasks 工具链不再使用
