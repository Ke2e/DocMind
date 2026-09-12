"""知识库表（任务 2.1，DDL 依据 `docs/adr/0001-knowledge-base-entity.md`）。

ADR-0001 定稿的形态：

    id BIGSERIAL PK / user_id → users.id / name VARCHAR(128) / description TEXT / created_at
    CREATE UNIQUE INDEX uq_kb_user_name ON knowledge_bases(user_id, name)

约束名 `uq_kb_user_name` 是 ADR 明文指定的，2.2 的验收要按这个名字查，
因此此处用**显式命名**（不交给 base.py 的 naming_convention 自动生成，
否则会变成 `uq_knowledge_bases_user_id`，只体现首列、语义也不对）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

#: 名称长度上限（ADR-0001 的 VARCHAR(128)）；4.1 的"超长名被拒"以此为界
KB_NAME_MAX_LENGTH = 128


class KnowledgeBase(Base):
    """用户的内容容器：文档归属与检索过滤的一等维度。"""

    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 归属用户。ADR-0001 未指定 ON DELETE，保持默认（有引用即拒绝删除）
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(KB_NAME_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # 同一用户下名称唯一（ADR-0001 第 4 条）。唯一索引同时承担"按用户列库"的过滤，
        # 故不再单独为 user_id 建普通索引——首列前缀已经覆盖。
        Index("uq_kb_user_name", "user_id", "name", unique=True),
    )
