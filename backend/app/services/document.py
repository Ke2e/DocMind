"""文档域逻辑（任务 5.1 – 5.5）。

三条贯穿全文件的规则（与前几组同一套口径，别各自发明）：

1. **每条读取都带用户维度过滤**（`AGENTS.md` §5 禁改清单），且**过滤写在语句里，
   不依赖调用方**：文档域显式带 `user_id`；取单个文档走 `get_owned_document`
   （把 `id` 与 `user_id` 放在同一条 WHERE，没有"忘记过滤"的机会）；
   `chunks` 表没有 `user_id` 列，故 `list_chunks` 用 `JOIN documents` 把它带进来。
   这是 D-038 整改第 4 组时定下的口径——"上面刚查过归属"不是能写进 SQL 的前提保证。
2. **归属不符一律回"不存在"（404）**，不用 403 —— 理由见 `services/knowledge_base.py`
   模块文档字符串（403 会把"他人资源是否存在"变成可探测信息）。
3. **写操作的"成功"以落库为准**（`AGENTS.md` §4）：所以下面两处 `commit` 都是刻意的，
   不是随手加的（见各自注释）。

`deleted_at IS NULL`（D-024）管的是 **`documents` 这一层**：`get_owned_document`、
`list_documents`、`list_chunks` 都带了；按知识库筛选时另加 `kb_id`。
（`chunks` 自己不需要墓碑列：片段不是独立资源，随文档的物理删除一并级联消失，
它的墓碑语义完全由所属文档表达。）

对外只暴露 `DocumentPublic` / `ChunkPublic`（`schemas/document.py`），
`storage_path` 这类服务端内部字段不出现在响应里。
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath
from typing import Final
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import (
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    UpstreamError,
    ValidationFailedError,
)
from app.core.lock import distributed_lock
from app.models import Chunk, Document, DocumentStatus, ProcessingTask
from app.models.document import ORIGINAL_FILENAME_MAX_LENGTH
from app.services.knowledge_base import get_owned_knowledge_base

logger = logging.getLogger(__name__)

_DOC_NOT_FOUND_MESSAGE = "文档不存在"

#: 投递锁的键前缀。粒度为 document_id（见 core/lock.py 的说明）。
DISPATCH_LOCK_KEY_PREFIX: Final = "docmind:lock:dispatch:"

#: 落盘与流式计数的读块大小。1MB 是"够大以摊薄系统调用、够小以不把内存撑起来"的折中；
#: 它只影响 IO 次数，不影响判定结果（判定按累计字节数）。
_STREAM_CHUNK_BYTES: Final = 1024 * 1024


# --------------------------------------------------------------------------
# 归属校验与读取
# --------------------------------------------------------------------------


async def get_owned_document(
    session: AsyncSession, *, user_id: int, document_id: int
) -> Document:
    """按"当前账号 + 文档 id"取文档，取不到即 404。

    `deleted_at IS NULL` 与归属条件写在同一句里：**已删除的文档对外就等于不存在**，
    不该回 410 或 403 —— 那会告诉调用方"这个 id 曾经存在过"。
    """
    document = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
    )
    if document is None:
        raise NotFoundError(_DOC_NOT_FOUND_MESSAGE)
    return document


async def list_documents(
    session: AsyncSession, *, user_id: int, kb_id: int | None = None
) -> Sequence[Document]:
    """列出当前账号的文档；给了 `kb_id` 就只列该库的（SC-008：按知识库筛选不跨库）。

    `kb_id` 的归属校验由**路由层**先用 `get_owned_knowledge_base` 完成：
    这样"他人知识库"与"不存在的知识库"都得到同一个 404，而不是回一个空列表
    （空列表会让调用方以为"库是我的，只是没有文档"）。

    排序按 `created_at` 降序 + `id` 降序：文档列表的自然预期是"刚传的在最上面"，
    与知识库列表的升序不同——知识库是长期存在的目录，文档是一次次追加的流。
    `id` 是必要的兜底：同一事务内批量插入可能取到同一个 `created_at`。
    """
    stmt = select(Document).where(
        Document.user_id == user_id, Document.deleted_at.is_(None)
    )
    if kb_id is not None:
        stmt = stmt.where(Document.kb_id == kb_id)
    stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc())
    return (await session.scalars(stmt)).all()


async def list_chunks(
    session: AsyncSession, *, user_id: int, document_id: int
) -> Sequence[Chunk]:
    """按 `chunk_index` 升序返回该文档的全部片段（FR-005）。

    **归属过滤写在这里，不靠调用方**：`chunks` 表没有 `user_id` 列，所以走
    `JOIN documents` 把它带进来，同时带上 `deleted_at IS NULL`。这是 D-038 定下的口径——
    文档域的每条语句都自带过滤，"上面刚查过归属"不是一条能被写进 SQL 的前提保证。
    调用方（路由）依然会先 `get_owned_document`：那是为了把"他人文档"与"文档不存在"
    收成同一个 404，与这里的过滤是两件事，不能互相替代。

    `(document_id, chunk_index)` 上的唯一约束首列前缀同时是该查询的索引
    （见 `models/chunk.py`），故不另建索引。
    """
    stmt = (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .where(
            Chunk.document_id == document_id,
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Chunk.chunk_index.asc())
    )
    return (await session.scalars(stmt)).all()


# --------------------------------------------------------------------------
# 5.1 / 5.2 上传受理
# --------------------------------------------------------------------------


def _extension_of(filename: str) -> str:
    """取小写扩展名（不含点）。用 `PurePosixPath` 而非 `Path`：客户端可能送 Windows 路径。"""
    return PurePosixPath(filename).suffix.lstrip(".").lower()


def _discard_partial_file(path) -> None:
    """删掉刚落下的半成品文件。**尽力而为，绝不把主错误吞掉。**

    用 `os.remove` 而不是 `Path.unlink`：语义相同，但本机沙箱的删除守卫会接管
    `Path.unlink`（见 findings D-041），`os.remove` 走的是更窄的那条路径。
    即便如此也**不把失败当致命**：调用这个函数时手里已经有一个更要紧的异常
    （磁盘写满、体积超限……），清理失败只该留一行日志，不该把 413 变成 500。
    """
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("半成品文件清理失败（不影响本次错误响应）：%s: %s", path, exc)


async def _stream_to_disk(
    upload: UploadFile, dest, *, max_bytes: int, max_mb: int
) -> int:
    """边读边写盘并累计字节数；一旦超限立刻中止。返回实际字节数。

    为什么不在读完 `await upload.read()` 后再判断大小：那样一份 50MB+ 的文件会先被
    完整读进内存/临时文件，既浪费又给"上传超大文件打内存"留了口子。
    这里按 1MB 分块前进，**在写盘前**判断累计值，超限即抛。

    写盘走 `asyncio.to_thread`：文件写入是阻塞 IO，直接在事件循环里做会让
    "上传期间服务仍能响应其他请求"（SC-001）变成空话。读那侧本来就是 async。

    与 `store_upload` 开头那次 `upload.size` 判定的分工：那一次是**快速闸门**
    （不碰磁盘，真实客户端都会撞在它上面）；这一条是**权威闸门**，
    数的是真正落盘的字节数，不信任任何上游声称的尺寸。
    """
    total = 0
    with dest.open("wb") as handle:
        while True:
            chunk = await upload.read(_STREAM_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise PayloadTooLargeError(
                    f"文件超出单文件体积上限（{max_mb}MB）",
                    detail={"max_upload_mb": max_mb},
                )
            await asyncio.to_thread(handle.write, chunk)
    return total


async def store_upload(
    session: AsyncSession,
    *,
    settings: Settings,
    user_id: int,
    kb_id: int,
    upload: UploadFile,
) -> Document:
    """校验 → 落盘 → 写 `uploaded` 记录。返回已提交的文档行。

    顺序是刻意的，四处都不能挪：

    1. **类型白名单最先**：纯字符串判断，不碰磁盘也不碰库。
    2. **归属校验在落盘之前**：越权提交不该在服务器上留下任何字节。
       （注意 multipart 报文此时已被框架收完，这里拦的是"写盘"而不是"收包"；
       收包侧的外层闸门是 nginx 的 `client_max_body_size`。）
    3. **体积上限在落盘之前**：`upload.size` 是框架的 multipart 解析器逐块累加出来的
       真实字节数（starlette 从 0 起累加，见 `datastructures.py` 的 `write`），
       所以超限请求在这里就能回绝，**一个字节都不落盘**——也就不存在"先写 51MB 再删"。
       `_stream_to_disk` 里的累计判定是第二条、也是权威的一条（不信任上游声称的尺寸）。
    4. **落盘在写库之前**：`file_size_bytes` 是流式统计出来的，必须先有实际字节数才能建行；
       写库失败时由 `except` 负责删掉刚落的文件，不留孤儿。

    **这里 commit 是刻意的**：调用方紧接着要在另一个进程（worker）里消费这条记录，
    而 worker 看不到未提交的行 —— 若把提交推迟到请求结束（`session_scope` 的收尾），
    投递出去的任务会在"文档还不存在"的窗口里被 worker 取走而失败。
    与第 4 组 D-031 的"换容器窗口里的写请求不可信"是同一类时序问题的另一面。
    """
    filename = (upload.filename or "").strip()
    extension = _extension_of(filename)
    allowed = settings.allowed_extensions
    if extension not in allowed:
        raise UnsupportedMediaTypeError(
            f"不支持的文件类型：{extension or '（无扩展名）'}",
            detail={"allowed_extensions": sorted(allowed)},
        )
    # 文件名长度护栏：`original_filename` 是 VARCHAR(512)，超长会以
    # `StringDataRightTruncation` 的形式从数据库冒上来变成 500（1.6 要挡的正是这类
    # 内部细节外泄）。上限取模型常量而不是另设配置项，理由见 `models/document.py`。
    # 选"拒绝"而不是"截断"：与 3.1 密码超长的处置一致 —— 截断是静默改数据。
    if len(filename) > ORIGINAL_FILENAME_MAX_LENGTH:
        raise ValidationFailedError(
            f"文件名过长（不超过 {ORIGINAL_FILENAME_MAX_LENGTH} 个字符）",
            detail={"max_filename_length": ORIGINAL_FILENAME_MAX_LENGTH},
        )

    await get_owned_knowledge_base(session, user_id=user_id, kb_id=kb_id)

    if upload.size is not None and upload.size > settings.max_upload_bytes:
        raise PayloadTooLargeError(
            f"文件超出单文件体积上限（{settings.MAX_UPLOAD_MB}MB）",
            detail={"max_upload_mb": settings.MAX_UPLOAD_MB},
        )

    upload_root = settings.upload_dir
    await asyncio.to_thread(upload_root.mkdir, parents=True, exist_ok=True)
    # 落盘文件名由服务端生成：客户端文件名只用于展示与扩展名判定，
    # 不参与路径拼接（否则一个 `../../x` 的"文件名"就能写到目录外）。
    storage_name = f"{uuid4().hex}.{extension}"
    destination = upload_root / storage_name

    try:
        size = await _stream_to_disk(
            upload,
            destination,
            max_bytes=settings.max_upload_bytes,
            max_mb=settings.MAX_UPLOAD_MB,
        )
        document = Document(
            user_id=user_id,
            kb_id=kb_id,
            original_filename=filename,
            storage_path=storage_name,
            file_type=extension,
            file_size_bytes=size,
            # 显式写初态，不依赖 DDL 的 server_default：`status` 要出现在响应体里，
            # 让它只有一个明确的来源，比依赖"驱动是否顺手把 server_default 带回来"更稳。
            # （第 4 组 D-036：别把"某个特性恰好帮我兜住了"当成设计。）
            status=DocumentStatus.UPLOADED,
        )
        session.add(document)
        await session.commit()
    except BaseException:
        # 半成品文件必须清掉：库里没有记录的文件就是纯垃圾（且会占满共享卷）
        await asyncio.to_thread(_discard_partial_file, destination)
        raise
    return document


# --------------------------------------------------------------------------
# 5.3 任务投递与并发保护
# --------------------------------------------------------------------------

#: 任务名必须与 `app/workers/tasks.py` 里注册的名字一致
PROCESS_DOCUMENT_TASK_NAME: Final = "app.workers.tasks.process_document"


def _default_enqueue(document_id: int) -> None:
    """把处理任务投给 Celery。

    用 `send_task` 按**任务名**投递，而不是 import 任务函数后 `.delay()`：
    API 进程不需要加载管线实现（6.x 会在那里引入解析与分块），只要能把消息放进 broker。

    `import` 放在函数体内是刻意的，不是随手：Celery 应用对象带着 broker 连接配置，
    在模块顶层建它会让"只想读一份文档详情"这类请求也去建一遍 broker 相关对象。
    真实投递路径（上传）只占少数请求，故把这份开销推迟到真正要投递时。
    """
    from app.workers.celery_app import celery_app

    celery_app.send_task(PROCESS_DOCUMENT_TASK_NAME, args=[document_id])


async def ensure_processing_task(session: AsyncSession, *, document_id: int) -> bool:
    """确保该文档有一条处理记录；返回**本次是否新建**。

    用 `INSERT ... ON CONFLICT DO NOTHING` 而不是"先 SELECT 再 INSERT"：
    后者在并发下有竞态（两个请求都查不到，然后一个插入失败）。
    `processing_tasks.document_id` 上的唯一约束是最终的裁判（design.md D4：
    幂等靠数据库唯一约束兜底，不靠先查再写）。
    """
    stmt = (
        pg_insert(ProcessingTask)
        .values(document_id=document_id, stage=DocumentStatus.UPLOADED)
        .on_conflict_do_nothing(index_elements=[ProcessingTask.document_id])
        .returning(ProcessingTask.id)
    )
    return await session.scalar(stmt) is not None


async def dispatch_processing_task(
    session: AsyncSession,
    client: aioredis.Redis,
    *,
    document_id: int,
    enqueue: Callable[[int], None] | None = None,
) -> bool:
    """**首次**投递该文档的处理任务；返回是否真的投递了。`enqueue=None` 时用 Celery。

    只在该文档尚无处理记录时投递。**这不是手动重试的入口**：8.2 的手动重试要复用
    已有记录并重置状态，走的是另一条路径（重置 + 投递），不要拿本函数当它用——
    本函数第二次调用会返回 `False` 且什么都不做。

    三道闸门，各管一段，缺一不可：

    | 闸门 | 挡住的场景 | 失效后果 |
    | --- | --- | --- |
    | Redis 分布式锁 | 两个并发请求同时做投递 | 多投递几次，但下面两层仍保证不重复 |
    | `ON CONFLICT DO NOTHING` | 任意时刻的重复投递 | 第二条处理记录 → 同一文档被并发处理 |
    | `deleted_at`（9.2 待加） | 已删除的文档被重新调度 | 给墓碑文档写回数据（9.2 的验收点） |

    拿不到锁时**直接返回 False**、不等待也不重试：此刻已有另一个投递在跑，
    而"任务行 + 投递"是原子的。真被卡住的任务由 8.3 的中断补偿扫描兜底（design.md D7）。
    """
    key = f"{DISPATCH_LOCK_KEY_PREFIX}{document_id}"
    async with distributed_lock(client, key) as acquired:
        if not acquired:
            return False
        if not await ensure_processing_task(session, document_id=document_id):
            return False
        # **先提交再投递，顺序不能反**：worker 是另一个进程，看不到未提交的行；
        # 反过来做，任务会在"处理记录还不存在"的窗口里被取走（结果未知，不可复现）。
        await session.commit()
        try:
            (enqueue or _default_enqueue)(document_id)
        except Exception as exc:  # noqa: BLE001 - broker 抖动/不可达，要翻译成可读错误
            logger.exception("文档处理任务投递失败：document_id=%s", document_id)
            raise UpstreamError(
                "文档已受理，但后台处理任务投递失败，请稍后重试或联系管理员"
            ) from exc
        return True
