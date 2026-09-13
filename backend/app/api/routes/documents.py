"""文档接口（任务 5.1 – 5.5）。

路由只做参数校验与编排，领域逻辑在 `app/services/document.py`。

**身份只来自凭证**：所有接口的 `user_id` 都取自 `get_current_user`，
请求体或查询参数里写的用户标识一律忽略（3.3 定的规矩）。

四个接口的分工：

| 方法 | 路径 | 任务 |
| --- | --- | --- |
| `POST` | `/api/documents` | 5.1 / 5.2 提交并立即受理（multipart：`file` + `kb_id`） |
| `GET` | `/api/documents` | 5.5 列表（可按 `kb_id` 筛选，不跨库） |
| `GET` | `/api/documents/{document_id}` | 5.5 详情 |
| `GET` | `/api/documents/{document_id}/chunks` | 5.4 片段反查 |

提交成功的状态码是 **201**（不是 202）：**正常路径**下接口确实创建了两个资源——
`documents` 行与 `processing_tasks` 行，而"文档标识"就是资源的标识。
（拿不到投递锁那条极窄路径下只会创建前者，此时记一条告警日志，见下。）
取舍与依据见 `docs/adr/0003`。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SettingsDep, get_current_user, get_db_session, get_redis_client
from app.models import Chunk, Document, User
from app.schemas.document import ChunkPublic, DocumentPublic
from app.services import document as doc_service
from app.services.knowledge_base import get_owned_knowledge_base

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _to_public(document: Document) -> DocumentPublic:
    return DocumentPublic(
        id=document.id,
        kb_id=document.kb_id,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size_bytes=document.file_size_bytes,
        status=document.status,
        error_message=document.error_message,
        chunk_count=document.chunk_count,
        created_at=document.created_at,
    )


def _chunk_to_public(chunk: Chunk) -> ChunkPublic:
    return ChunkPublic(
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        token_count=chunk.token_count,
    )


@router.post(
    "",
    response_model=DocumentPublic,
    status_code=status.HTTP_201_CREATED,
    summary="提交文档并立即受理",
)
async def upload_document(
    file: Annotated[UploadFile, File(description="待提交的文件（pdf / docx / md / txt）")],
    kb_id: Annotated[int, Form(description="归属知识库 id", ge=1)],
    settings: SettingsDep,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    redis_client=Depends(get_redis_client),
) -> DocumentPublic:
    """校验 → 落盘 → 写 `uploaded` 记录 → 投递处理任务 → 立即返回。

    **MUST NOT 等待解析完成**（规格「提交文档并立即受理」）：请求里只做上面四步，
    解析 / 清洗 / 分块全部在 worker 侧（6.x），故 10MB 的提交也在秒级返回（SC-001）。
    """
    document = await doc_service.store_upload(
        session,
        settings=settings,
        user_id=current_user.id,
        kb_id=kb_id,
        upload=file,
    )
    dispatched = await doc_service.dispatch_processing_task(
        session, redis_client, document_id=document.id
    )
    if not dispatched:
        # 极窄路径：该文档立即就被另一个投递者抢先（或锁仍被占）。文档已受理是对的，
        # 但"后台会处理它"这件事此刻没有保证 —— 记告警，并靠 8.3 的中断补偿扫描兜底
        # （它扫的正是"停在中间态"的处理记录，见 design.md D7）。
        logger.warning(
            "文档已受理但本次未投递处理任务：document_id=%s（等 8.3 补偿扫描重调度）",
            document.id,
        )
    return _to_public(document)


@router.get("", response_model=list[DocumentPublic], summary="列出当前账号的文档")
async def list_documents(
    kb_id: Annotated[int | None, Query(ge=1, description="只列该知识库的文档")] = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[DocumentPublic]:
    """不给 `kb_id` 时返回全部；给了就只返回该库的（SC-008：筛选不跨库）。

    `kb_id` 属于他人或不存在时回 **404** 而不是空列表：空列表会让调用方以为
    "库是我的，只是里面没文档"，把"库不是你的"这件事藏起来。
    """
    if kb_id is not None:
        await get_owned_knowledge_base(session, user_id=current_user.id, kb_id=kb_id)
    documents = await doc_service.list_documents(
        session, user_id=current_user.id, kb_id=kb_id
    )
    return [_to_public(document) for document in documents]


@router.get(
    "/{document_id}", response_model=DocumentPublic, summary="查询文档详情"
)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentPublic:
    """他人（或不存在、或已删除）的文档一律 404。"""
    document = await doc_service.get_owned_document(
        session, user_id=current_user.id, document_id=document_id
    )
    return _to_public(document)


@router.get(
    "/{document_id}/chunks",
    response_model=list[ChunkPublic],
    summary="反查某文档的全部片段",
)
async def list_document_chunks(
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ChunkPublic]:
    """按 `chunk_index` 升序返回全部片段（FR-005）。

    先经 `get_owned_document` 定归属，是为了把"他人的文档"与"不存在的文档"收成同一个
    404；片段查询自身也带了归属过滤（`list_chunks` 里 JOIN 文档），两层不能互相替代。
    """
    document = await doc_service.get_owned_document(
        session, user_id=current_user.id, document_id=document_id
    )
    chunks = await doc_service.list_chunks(
        session, user_id=current_user.id, document_id=document.id
    )
    return [_chunk_to_public(chunk) for chunk in chunks]
