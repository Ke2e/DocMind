"""SQLAlchemy ORM 模型包（任务 2.1）。

五张表在此聚合导出：应用代码与 Alembic 都从本包取 `Base`，
只要 `import app.models` 就保证 5 张表全部注册进 `Base.metadata`（漏 import 的表
autogenerate 时会凭空生成 DROP，是这类项目最常见的迁移事故）。

子模块统一 `from app.models.base import Base`，不反向导入本包——`base.py` 独立于
聚合层，不存在循环依赖（OneHub 把 Base 定义在包 `__init__` 里，靠导入顺序绕开，
这里换成更直白的写法）。
"""

from app.models.base import Base
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import STATUS_SEQUENCE, DocumentStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.processing_task import ProcessingTask
from app.models.user import User

__all__ = [
    "Base",
    "DocumentStatus",
    "STATUS_SEQUENCE",
    "User",
    "KnowledgeBase",
    "Document",
    "Chunk",
    "ProcessingTask",
]
