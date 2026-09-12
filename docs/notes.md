# notes.md — teach 讲解笔记

> 配合每周 teach 主题，讲清"为什么这样设计"与"换种做法会怎样"。由 AI 讲解后沉淀于此。

## W5（未开始）

- FastAPI：依赖注入与请求生命周期、为什么异步路由里不能跑 CPU 密集解析
- SQLAlchemy 2.0：async session 与同步 ORM 的差异、Alembic 迁移只增不改的原因
- JWT / RBAC：无状态凭证的取舍、刷新策略、为什么隔离条件要下沉到查询层
- Celery：为什么解析必须出栈到 worker、任务状态持久化与幂等、中断补偿

## W6（未开始）

- Embedding 原理：为什么相似度可用余弦、bge-m3 的多粒度
- Milvus / HNSW：索引参数（M / efConstruction）对召回与耗时的影响
- SSE 生成端 vs OneHub 转发端：两种流式场景的差异

## W7（未开始）

- 分块策略：固定/递归/语义切分的取舍，overlap 为什么必要
- PG 全文检索：tsvector / 排序相关性
- RRF：为什么用排名倒数融合而不是分数归一
- 重排：bi-encoder vs cross-encoder
- 多轮记忆：滑动窗口与摘要压缩

## W8（未开始）

- 手写 mini-agent：tool_calls 循环、消息历史管理、终止判定
- LangGraph：框架封装了什么、与手写实现的对照
- CRAG / Self-RAG：自我评估与重试的动机

## W10（未开始）

- 语义缓存：相似度阈值与误命中代价
- 幻觉治理与 RAGAS：忠实度 / 答案相关性 / 上下文精确率
- Docker 编排：健康检查与启动顺序
