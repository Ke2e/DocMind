"""文档处理状态（任务 2.1，供 `documents.status` 与 `processing_tasks.stage` 共用）。

状态机（FR-003 / design.md D3）：

    uploaded(已接收) → parsing(解析中) → chunking(分块中) → [vectorizing] → ready(完成)
    任一中间态 ——异常——> failed(失败)；failed 经手动重试回到 uploaded

- `vectorizing` 是 002 启用的阶段位，本期只保留取值、不进入该状态（Q2 结论）。
- 入库值就是英文小写取值，中文展示文案由接口层（7.1 / 7.2）翻译，
  不把展示文案固化进数据库，也不让数据库承担文案变更。
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum


class DocumentStatus(str, Enum):
    """文档处理状态。取值即入库值，不可随意重命名（已有数据按值匹配）。"""

    UPLOADED = "uploaded"  # 已接收
    PARSING = "parsing"  # 解析中
    CHUNKING = "chunking"  # 分块中
    VECTORIZING = "vectorizing"  # 向量化（002 启用，本期不进入）
    READY = "ready"  # 完成
    FAILED = "failed"  # 失败


#: 推进顺序（不含终态 failed）。7.1 的"已完成阶段"与 6.4 的"不回退"校验都以它为准，
#: 定义在此处是为了避免这两个地方各自维护一份顺序而漂移。
STATUS_SEQUENCE: tuple[DocumentStatus, ...] = (
    DocumentStatus.UPLOADED,
    DocumentStatus.PARSING,
    DocumentStatus.CHUNKING,
    DocumentStatus.VECTORIZING,
    DocumentStatus.READY,
)


#: 共用的列类型：`native_enum=False` → 落库为 VARCHAR，迁移免去 PG 原生枚举的 ALTER TYPE 之痛。
#: `values_callable` 保证按枚举取值（小写英文）而不是成员名（大写）入库。
DOCUMENT_STATUS_TYPE = SAEnum(
    DocumentStatus,
    name="document_status",
    native_enum=False,
    length=20,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)
