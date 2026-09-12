"""片段表（任务 2.1）。

字段来源：Key Entities 的 Chunk（所属文档 / 顺序序号 / 文本内容 / 长度计量）。

`(document_id, chunk_index)` 唯一约束是 design.md D4 的落地方式：幂等不靠"先查再写"
（有竞态），而靠"同一事务内先清后写 + 唯一约束兜底"。该约束的首列前缀同时承担
"按文档反查全部片段"（FR-005）的索引职责，故不另建 document_id 单列索引。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Chunk(Base):
    """文档切分后的文本单元，随文档物理删除而级联移除。"""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 显式命名（自动命名只会取首列，产出 uq_chunks_document_id，语义不准）
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE")
    )
    # 顺序序号，从 0 开始；反查接口按它升序返回（5.4）
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # 长度计量：tiktoken 计数（与分块参数同一计量单位，6.2）
    token_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_chunks_document_chunk_index"
        ),
    )
