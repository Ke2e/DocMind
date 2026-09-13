"""文档与片段的请求 / 响应模型（任务 5.1–5.5）。

判据来源：`openspec/changes/add-doc-ingest-pipeline/specs/document-ingest/spec.md`
与 `specs/001-doc-ingest-pipeline/spec.md` 的 Key Entities（Document / Chunk）。

两处刻意的取舍：

1. **`DocumentPublic` 不带 `storage_path`**。Key Entities 里确实有"存储位置"这一属性，
   但它是**服务端落盘路径**（`UPLOAD_DIR` 下的相对路径），对外暴露只会给攻击面
   （暴露目录结构）而前端一无所用 —— 1.6 的硬约束是"错误响应不含内部细节"，
   同一条理由适用于正常响应的**内部字段**：不该给的就不给。
   它仍然落库（worker 要靠它读文件），只是不出现在对外视图里。
2. **`status` 用枚举而不是裸字符串**。取值集合即 `DocumentStatus`，响应体里序列化为
   入库值（`uploaded` / `parsing` / …）。用 `str` 的话，某天状态机加了新取值、
   这里静默跟着变，类型层面看不出任何约束。中文展示文案由 7.x 的接口层翻译，
   不在这里固化（与 `models/enums.py` 的分工一致）。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus

__all__ = ["DocumentPublic", "ChunkPublic"]


class DocumentPublic(BaseModel):
    """文档的对外视图（列表与详情共用）。"""

    id: int
    kb_id: int = Field(description="归属知识库 id")
    original_filename: str = Field(description="用户上传时的原始文件名，仅作展示")
    file_type: str = Field(description="小写扩展名，不含点")
    file_size_bytes: int
    status: DocumentStatus = Field(description="处理状态，序列化为入库值")
    error_message: str | None = Field(
        default=None, description="可读失败原因；未失败时为 null"
    )
    chunk_count: int = Field(description="片段数量（0 表示尚未切分出片段）")
    created_at: datetime


class ChunkPublic(BaseModel):
    """一个片段（5.4 反查接口用）。

    只暴露 `chunk_index` / `content` / `token_count`：`document_id` 对调用方是已知条件
    （它就在请求路径里），回显无意义；`id` 是内部主键，反查排序一律以 `chunk_index` 为准。
    """

    chunk_index: int = Field(description="顺序序号，从 0 开始")
    content: str
    token_count: int = Field(description="按 tiktoken 计的长度，与分块参数同一计量单位")
