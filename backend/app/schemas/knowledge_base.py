"""知识库相关的请求 / 响应模型（任务 4.1 / 4.2）。

判据来源：`openspec/changes/add-doc-ingest-pipeline/specs/knowledge-base/spec.md`
的「创建知识库」「知识库列表」「重命名知识库」「删除知识库」四个 Requirement。

两个刻意的设计取舍：

1. **名称长度上限取自模型常量**（`KB_NAME_MAX_LENGTH` = DDL 的 `VARCHAR(128)`），
   不另写一个字面量 —— 否则改 DDL 时这里会悄悄与数据库脱节，表现为"接口放过、
   数据库 `StringDataRightTruncation`"，正是 1.6 想避免的那类内部细节外泄。
2. **归一化放在 `mode="before"` 的校验器里**（先 strip 再判长度），而不是只写
   `Field(min_length=1, max_length=128)`。后者先按原始串判长，会把
   `"  " + 128 个字符` 这种"归一化后合法"的名称误杀。
   与 `schemas/auth.py` 的用户名规则保持同一套口径：两端空白无意义。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.knowledge_base import KB_NAME_MAX_LENGTH

__all__ = [
    "KnowledgeBaseCreateRequest",
    "KnowledgeBaseUpdateRequest",
    "KnowledgeBasePublic",
]


def normalize_kb_name(value: str) -> str:
    """两端空白无意义；去空白后不能为空、不能超长。

    大小写**不**归一：与「用户名区分大小写」保持同一口径，`Docs` 与 `docs`
    是两个不同的库。规格未规定此项，故沿用已定案的同类规则而不是自创一套。
    """
    name = value.strip()
    if not name:
        raise ValueError("知识库名称不能为空")
    if len(name) > KB_NAME_MAX_LENGTH:
        raise ValueError(f"知识库名称长度不超过 {KB_NAME_MAX_LENGTH} 个字符")
    return name


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(description="知识库名称，同账号下唯一")
    # description 不在 knowledge-base 规格里，但 ADR-0001 已批准的 DDL 有该列（TEXT、可空），
    # 故按"可选、不设长度上限"暴露：不设上限是因为规格与 ADR 都没给这个界，不自行发明约束。
    description: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return normalize_kb_name(value) if isinstance(value, str) else value


class KnowledgeBaseUpdateRequest(BaseModel):
    """重命名（4.1）。名称规则与创建**完全一致**（规格明文要求）。"""

    name: str = Field(description="新名称，与创建同一套规则")
    description: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return normalize_kb_name(value) if isinstance(value, str) else value


class KnowledgeBasePublic(BaseModel):
    """知识库的对外视图。

    `document_count` 是**计算字段**（不属于 knowledge_bases 表）：只统计
    `documents.deleted_at IS NULL` 的行 —— 墓碑文档不算数，否则"删空文档后
    知识库仍显示非空、且删不掉"，见 docs/findings.md D-024。
    因此本模型**不带 `from_attributes`**：它从来不是直接由 ORM 对象转换出来的，
    而是 service 层查出 `(kb, count)` 后显式组装的。留一个用不上的 config
    只会让读代码的人以为某处真的在做 ORM 映射。
    """

    id: int
    name: str
    description: str | None = None
    document_count: int = Field(description="该库下未删除（deleted_at IS NULL）的文档数量")
    created_at: datetime
