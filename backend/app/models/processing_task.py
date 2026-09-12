"""处理任务表（任务 2.1）。

字段来源：Key Entities 的 Processing Task（关联文档 / 当前阶段 / 自动重试次数 /
手动重试次数 / 最近一次执行时间），用于支撑进度查询、重试与中断识别。

与 `documents` 的分工（design.md D3）：`documents.status` 是查询用的权威当前状态，
本表记录"这次执行的阶段 + 两个重试计数 + 最近执行时间"。
`stage` 与 `documents.status` 由 6.4 的单一状态迁移方法**在同一事务内成对更新**，
本表存在的意义是让 8.3 的卡死扫描（"中间态 + last_run_at 超阈值"）只读一张表、不必 join。

`document_id` 唯一：5.3 要求"并发提交同一文档两次只产生一条处理记录"，
重试复用同一条记录、只累加计数，因此一个文档恒对应一行。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import DOCUMENT_STATUS_TYPE, DocumentStatus


class ProcessingTask(Base):
    """一次文档处理的执行记录（每文档一行）。"""

    __tablename__ = "processing_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE")
    )
    # 该次执行所处阶段（与 documents.status 同事务成对更新）
    stage: Mapped[DocumentStatus] = mapped_column(
        DOCUMENT_STATUS_TYPE, server_default=DocumentStatus.UPLOADED.value
    )
    # 自动重试计数（上限 AUTO_RETRY_MAX）
    auto_retry_count: Mapped[int] = mapped_column(Integer, server_default="0")
    # 手动重试计数（上限 MANUAL_RETRY_MAX）
    manual_retry_count: Mapped[int] = mapped_column(Integer, server_default="0")
    # 最近一次执行时间：8.3 的卡死阈值（STUCK_TASK_THRESHOLD_SECONDS）以它为基准
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("document_id", name="uq_processing_tasks_document_id"),
    )
