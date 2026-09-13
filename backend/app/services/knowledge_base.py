"""知识库领域逻辑（任务 4.1 / 4.2）。

两条贯穿全文件的规则：

1. **每条查询都带用户维度过滤**（AGENTS.md §5 禁改清单；constitution 的同名红线）。
   做法分两层，都是"写在同一条件里"而不是"取出来再比对"：
   - 知识库域：取单个库的唯一入口是 `get_owned_knowledge_base`，把 `id` 与 `user_id`
     放在**同一条 WHERE** 里 —— 后者只要有人漏写那一步就越权，而前者没有"忘记过滤"的机会；
   - 文档域：`count_live_documents` 与删库时的墓碑清除同样显式带 `user_id`。
     （删库路径其实已由 `get_owned_knowledge_base` 先验过归属，这里再带一次是纵深防御：
     计数与删除是**两个**语句，中间的归属前提不该靠"读代码的人记得上面查过"来保证。）
2. **归属不符一律回"不存在"**。规格只要求"拒绝且不修改数据"，这里选 404 而非 403：
   403 等于承认"这个 id 真实存在，只是不属于你"，把他人资源的存在性变成了可探测信息。
   与 3.2 的"登录失败不区分两种原因"是同一个思路。

文档数量的口径（D-024 衔接点）：只统计 `documents.deleted_at IS NULL` 的行。
墓碑行不算文档，否则 9.1 删完文档后知识库会永久显示非空、且永远删不掉。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models import Document, KnowledgeBase

_NAME_TAKEN_MESSAGE = "该名称的知识库已存在，请换一个"
_KB_NOT_FOUND_MESSAGE = "知识库不存在"
_NON_EMPTY_MESSAGE = "该知识库下仍有文档，请先清空后再删除"

#: 区分"没传 description"与"显式传了 null"的哨兵。
#:
#: 重命名接口是 PATCH 语义：只改名、不传简介时**不能**把已有简介清空。
#: 若把缺省值写成 `None`，两者就再也分不开了（`None` 既是缺省也是合法取值），
#: 结果是"改个名字顺手删掉简介"——一条静默的数据丢失。
UNSET: Final = object()


async def get_owned_knowledge_base(
    session: AsyncSession, *, user_id: int, kb_id: int
) -> KnowledgeBase:
    """按"当前账号 + 知识库 id"取库，取不到即 404。

    不区分"不存在"与"属于别人"——**别改成 403**，理由见模块文档字符串。
    5.2 的"向他人知识库提交被拒"也复用本函数。
    """
    kb = await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id
        )
    )
    if kb is None:
        raise NotFoundError(_KB_NOT_FOUND_MESSAGE)
    return kb


async def count_live_documents(
    session: AsyncSession, *, user_id: int, kb_id: int
) -> int:
    """该库下**未被删除**的文档数量。

    `deleted_at IS NULL` 这一半是关键，不能简化成 `count(*)`：见模块文档字符串。
    `user_id` 也一并带上（纵深防御），别因为"调用方刚查过归属"就省掉。
    """
    total = await session.scalar(
        select(func.count(Document.id)).where(
            Document.user_id == user_id,
            Document.kb_id == kb_id,
            Document.deleted_at.is_(None),
        )
    )
    return int(total or 0)


async def list_knowledge_bases(
    session: AsyncSession, *, user_id: int
) -> Sequence[tuple[KnowledgeBase, int]]:
    """列出当前账号的知识库，附带各自的文档数量。

    用 `LEFT OUTER JOIN ... ON` 把过滤条件写进 **JOIN 的 ON 子句**（而不是 WHERE）：
    放进 WHERE 会把"零文档的库"整行滤掉（LEFT JOIN 退化成 INNER JOIN），
    表现为新用户建完库却看不到自己的空库。

    排序带 `id` 兜底：`created_at` 有 `server_default=now()`，同一事务里批量插入
    可能取到同一时刻，只按它排序结果不稳定。
    """
    stmt = (
        select(KnowledgeBase, func.count(Document.id).label("document_count"))
        .outerjoin(
            Document,
            and_(Document.kb_id == KnowledgeBase.id, Document.deleted_at.is_(None)),
        )
        .where(KnowledgeBase.user_id == user_id)
        .group_by(KnowledgeBase.id)
        .order_by(KnowledgeBase.created_at.asc(), KnowledgeBase.id.asc())
    )
    rows = (await session.execute(stmt)).all()
    return [(kb, int(count)) for kb, count in rows]


async def create_knowledge_base(
    session: AsyncSession,
    *,
    user_id: int,
    name: str,
    description: str | None = None,
) -> KnowledgeBase:
    """创建知识库。归属由**调用方传入的 user_id** 决定，不读请求体。

    重名先查一次只是为了给可读提示；唯一性最终由 `uq_kb_user_name` 兜底 ——
    "先查后写"在并发下必有竞态，所以下面还接住了 IntegrityError（与 3.1 注册同一套路）。
    """
    existing = await session.scalar(
        select(KnowledgeBase.id).where(
            KnowledgeBase.user_id == user_id, KnowledgeBase.name == name
        )
    )
    if existing is not None:
        raise ConflictError(_NAME_TAKEN_MESSAGE)

    kb = KnowledgeBase(user_id=user_id, name=name, description=description)
    session.add(kb)
    try:
        await session.flush()
    except IntegrityError as exc:
        # 两个请求同时通过了上面的检查，唯一索引会拦下后到的那个
        raise ConflictError(_NAME_TAKEN_MESSAGE) from exc
    return kb


async def rename_knowledge_base(
    session: AsyncSession,
    *,
    user_id: int,
    kb_id: int,
    name: str,
    description: str | None | object = UNSET,
) -> KnowledgeBase:
    """重命名，可选同时改简介。`description` 不传（`UNSET`）则保留原值。

    重命名为**自己当前的名称**是允许的（幂等），所以重名检查里排除了自己，
    否则"把 A 改成 A"会莫名报 409。
    """
    kb = await get_owned_knowledge_base(session, user_id=user_id, kb_id=kb_id)

    if name != kb.name:
        clash = await session.scalar(
            select(KnowledgeBase.id).where(
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.name == name,
                KnowledgeBase.id != kb_id,
            )
        )
        if clash is not None:
            raise ConflictError(_NAME_TAKEN_MESSAGE)

    kb.name = name
    if description is not UNSET:
        kb.description = description  # type: ignore[assignment]
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(_NAME_TAKEN_MESSAGE) from exc
    return kb


async def delete_knowledge_base(
    session: AsyncSession, *, user_id: int, kb_id: int
) -> None:
    """删除知识库。**非空拒删**（规格「删除知识库」）。

    非空时拒绝并回未清空的数量——这个数字让前端能直接说"还有 3 份文档没删"。
    刻意不做级联删除：后台 worker 可能正在处理该库的文档，级联会把"处理中的文档"
    连同它们的处理记录一起蒸发，变成谁也查不清的静默丢失（ADR-0001 的取舍）。

    空库（含**只剩墓碑行**的库）才走到物理删除。墓碑行必须先清掉：
    `fk_documents_kb_id_knowledge_bases` 是不级联的 RESTRICT，"非空拒删"的第二道闸门，
    留着墓碑行直接删库会被它拦住（D-024 交给本组的衔接点）。
    """
    kb = await get_owned_knowledge_base(session, user_id=user_id, kb_id=kb_id)

    live = await count_live_documents(session, user_id=user_id, kb_id=kb_id)
    if live:
        raise ConflictError(
            f"该知识库下还有 {live} 份文档，请先清空后再删除",
            detail={"document_count": live},
        )

    # 只剩墓碑行（或本来就空）：物理清除墓碑文档，chunks / processing_tasks 由
    # 两张表上的 ON DELETE CASCADE 一并带走，无需在这里手工删。
    #
    # **只删墓碑行**（`deleted_at IS NOT NULL`），不写成"删该库全部文档"：后者把正确性
    # 押在"上面那次计数之后没有新文档落进来"这个假设上；一旦并发插入真的发生，
    # 它会连那份刚上传的文档一起删掉 —— 静默的数据丢失，比直接报错严重得多。
    # 只删墓碑行的话，并发落进来的在册文档会留下来、并被外键拦下，走下面的 409 分支。
    try:
        await session.execute(
            delete(Document).where(
                Document.user_id == user_id,
                Document.kb_id == kb_id,
                Document.deleted_at.is_not(None),
            )
        )
        await session.delete(kb)
        await session.flush()
    except IntegrityError as exc:
        # 计数与删库之间存在并发窗口：计数完之后又有在册文档落进这个库，
        # 外键（RESTRICT）会拦下删库。这仍属"非空拒删"的语义，翻译成 409，
        # 别让 500 冒到用户面前（也让日志里少一条无意义的栈）。
        raise ConflictError(_NON_EMPTY_MESSAGE) from exc
