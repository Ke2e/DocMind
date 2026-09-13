"""文档表（任务 2.1）。

字段清单来源：`specs/001-doc-ingest-pipeline/spec.md` Key Entities 的 Document
（FR-018：原始文件名 / 类型 / 字节大小 / 状态 / 失败原因 / 片段数量 / 归属知识库 / 创建时间），
外加 design.md D8 要求的删除标记。

**关于 `deleted_at`（软删除标记）**：D8 与任务 9.1 明确要求两件事并存——
"级联清除片段与处理记录" + "删除标记阻止写回"。两者分工：

1. 删除请求在同一事务内写 `deleted_at`（墓碑），并**物理删除**该文档的 chunks 与
   processing_tasks（9.1 的"级联清除"；也由下方 FK 的 ON DELETE CASCADE 兜底）。
2. 所有读取路径一律带 `deleted_at IS NULL`；worker 每次写回前在同一事务内复查该标记，
   命中墓碑即放弃写入（9.2"删除立即生效，不再产生新片段"）。
3. 文档行本身保留为墓碑，直到所属知识库被删除时一并物理清除——知识库"非空拒删"的
   计数只统计非墓碑文档，因此不会因墓碑残留而误判为非空（4.2）。

`kb_id` 的外键保持默认（有引用即拒绝删除），是"非空知识库拒删"在数据库层的第二道闸门。
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import DOCUMENT_STATUS_TYPE, DocumentStatus

#: `original_filename` 的长度上限 —— 取自 DDL（`VARCHAR(512)`），不另设配置项。
#: 与 `KB_NAME_MAX_LENGTH` 同一口径：它是**列的形状**而不是可调业务参数，
#: 抄成另一个字面量迟早与数据库脱节，届时表现为"接口放过、DB 报
#: `StringDataRightTruncation`"（正是 1.6 要挡住的内部细节外泄）。
ORIGINAL_FILENAME_MAX_LENGTH: Final = 512


class Document(Base):
    """一份被上传的原始文件及其处理状态。"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 归属用户：所有查询都必须带此过滤（AGENTS.md §5「禁改清单」）
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    # 归属知识库：ADR-0001 规定 NOT NULL
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_bases.id"))
    # 原始文件名：仅作展示，不参与落盘命名（同名文件按新文档处理，见 Assumptions）
    original_filename: Mapped[str] = mapped_column(String(ORIGINAL_FILENAME_MAX_LENGTH))
    # 落盘位置：相对 UPLOAD_DIR 的路径，api 与 worker 共享卷
    storage_path: Mapped[str] = mapped_column(String(1024))
    # 文件类型：小写扩展名、不含点（与 config.allowed_extensions 同一口径）
    file_type: Mapped[str] = mapped_column(String(16))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    # 当前阶段。与 processing_tasks.stage 由 6.4 的单一状态迁移方法成对写入
    status: Mapped[DocumentStatus] = mapped_column(
        DOCUMENT_STATUS_TYPE, server_default=DocumentStatus.UPLOADED.value
    )
    # 可读失败原因（FR-007）；只存面向用户的文案，内部堆栈只进日志
    error_message: Mapped[str | None] = mapped_column(Text)
    # 片段数量：列表展示用；与 chunks 实际行数的一致性由 6.4 验收
    # 用 text("0") 而不是字符串 "0"：后者在 DDL 里会渲染成 DEFAULT '0'（靠 PG 隐式转换）
    chunk_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # 删除标记（D8）：非空即视为已删除，写入前校验
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # ADR-0001 明文要求、2.2 按名字验收
        Index("idx_documents_kb", "kb_id"),
    )
