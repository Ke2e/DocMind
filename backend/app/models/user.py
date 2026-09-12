"""账号表（任务 2.1）。

表结构形态沿用 OneHub 的 `users`（唯一登录名 + 只存密码摘要 + 创建时间），
差异是登录名用 `username` 而非 `email`：本增量的账号规格是"用户名 + 密码"，
且本期不做邮箱验证，引入 email 属于无据字段。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """平台账号：用户名全局唯一，密码只存不可还原摘要。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 3.1 要求"同一用户名唯一占用"：唯一约束兜底，接口层负责给可读提示
    username: Mapped[str] = mapped_column(String(64))
    # 不可还原摘要（具体算法待 3.1 的 ADR 批准）；长度按 argon2id 输出留余量
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)
