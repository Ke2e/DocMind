"""知识库接口（任务 4.1 / 4.2）。

路由只做参数校验与编排，领域逻辑在 `app/services/knowledge_base.py`。

**身份只来自凭证**：所有接口的 `user_id` 都取自 `get_current_user`，
请求体或查询参数里写的用户标识一律忽略（3.3 定的规矩，4.1 起有了真正的越权写入口，
故在此补上端到端用例）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models import KnowledgeBase, User
from app.schemas.knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBasePublic,
    KnowledgeBaseUpdateRequest,
)
from app.services import knowledge_base as kb_service

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])


def _to_public(kb: KnowledgeBase, document_count: int) -> KnowledgeBasePublic:
    return KnowledgeBasePublic(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        document_count=document_count,
        created_at=kb.created_at,
    )


@router.get(
    "",
    response_model=list[KnowledgeBasePublic],
    summary="列出当前账号的知识库",
)
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[KnowledgeBasePublic]:
    """只返回自己的知识库，每条带该库当前的文档数量。"""
    rows = await kb_service.list_knowledge_bases(session, user_id=current_user.id)
    return [_to_public(kb, count) for kb, count in rows]


@router.post(
    "",
    response_model=KnowledgeBasePublic,
    status_code=status.HTTP_201_CREATED,
    summary="创建知识库",
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeBasePublic:
    kb = await kb_service.create_knowledge_base(
        session,
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
    )
    # 不需要 refresh：SQLAlchemy 2.0 在支持 RETURNING 的后端（asyncpg 就是）上会于
    # INSERT ... RETURNING 里带回 server_default 生成的 id 与 created_at。
    # 这是实测结论（去掉 refresh 后建库用例仍全绿），不是为了省一次查询而想当然。
    return _to_public(kb, 0)


@router.patch(
    "/{kb_id}",
    response_model=KnowledgeBasePublic,
    summary="重命名知识库",
)
async def rename_knowledge_base(
    kb_id: int,
    payload: KnowledgeBaseUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeBasePublic:
    """重命名。他人（或不存在）的知识库一律 404，且不修改任何数据。

    `description` 只在请求体**显式带上**时才更新（PATCH 语义）：
    `model_fields_set` 能区分"没传"与"传了 null"，否则改个名字会顺手清空简介。
    """
    kb = await kb_service.rename_knowledge_base(
        session,
        user_id=current_user.id,
        kb_id=kb_id,
        name=payload.name,
        description=(
            payload.description
            if "description" in payload.model_fields_set
            else kb_service.UNSET
        ),
    )
    count = await kb_service.count_live_documents(
        session, user_id=current_user.id, kb_id=kb.id
    )
    return _to_public(kb, count)


@router.delete(
    "/{kb_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除知识库（非空拒删）",
)
async def delete_knowledge_base(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """删除空知识库。仍含文档时返回 409，并在 `detail.document_count` 给出未清空数量。"""
    await kb_service.delete_knowledge_base(
        session, user_id=current_user.id, kb_id=kb_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
