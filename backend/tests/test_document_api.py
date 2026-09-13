"""第 5 组（文档上传与受理 5.1–5.5）接口层验收。

**测试环境与生产的两处刻意差异**（都在 `upload_root` fixture 里设定，别在这里重复）：

1. `UPLOAD_DIR` 指向 `uploads/_pytest`，不写进开发者本机真正在用的 `uploads/`；
2. `MAX_UPLOAD_MB` 被压到 **2**，故"超限"路径用 3MB 载荷即可覆盖边界，
   真实的 50MB 上限由 `tools/verify_document_e2e.py` 用真实配置验（10MB PDF + 51MB 请求）。

**两条通用规矩**（前四组踩出来的）：

- 写操作一律以**查库**为准，不只看接口回了 201；
- 越权用例除了断言状态码，还要断言"数据没变 / 没产生新行"——只回 404 但偷偷落了数据同样是错。

**"没落盘"怎么断言**：用目录的**前后快照**比对，不断言目录为空。测试专用的上传目录
不做收尾清理（理由见 `conftest.py::upload_root`），它天然会攒下历史运行的文件。

本文件里 chunk 数据一律由 `db_session` 直接造：片段是 6.x 的产物（5.x 还没有分块器），
而被测的是 5.4 的**读取**逻辑。这与第 4 组用 `stub_document` 造文档是同一个取舍。
"""

from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document, DocumentStatus, ProcessingTask
from app.models.document import ORIGINAL_FILENAME_MAX_LENGTH
from app.services import document as doc_service

if TYPE_CHECKING:  # 只在类型层引用：runtime 下 tests/ 不是包，别真去 import 它
    from tests.conftest import Account

PDF_BODY = b"%PDF-1.4\n% DocMind 5.x test payload\n%%EOF\n"
DOCS = "/api/documents"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def _files(root: Path) -> set[str]:
    """上传目录的文件名快照（用于断言"确实没落盘"）。"""
    return {entry.name for entry in root.iterdir() if entry.is_file()}


async def _create_kb(client: AsyncClient, account: Account, name: str) -> int:
    resp = await client.post(
        "/api/knowledge-bases", json={"name": name}, headers=account.auth_header
    )
    assert resp.status_code == 201, resp.text
    return int(resp.json()["id"])


def _upload(
    client: AsyncClient,
    account: Account,
    *,
    kb_id: int,
    filename: str = "手册.pdf",
    body: bytes = PDF_BODY,
):
    return client.post(
        DOCS,
        files={"file": (filename, body, "application/octet-stream")},
        data={"kb_id": str(kb_id)},
        headers=account.auth_header,
    )


async def _count(session: AsyncSession, model) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def _task_count(session: AsyncSession, document_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count(ProcessingTask.id)).where(
                ProcessingTask.document_id == document_id
            )
        )
        or 0
    )


async def _stub_document(session: AsyncSession, *, user_id: int, kb_id: int) -> int:
    """直接造一条 `uploaded` 文档（5.3 只测投递逻辑，不关心"文档怎么来的"）。"""
    document = Document(
        user_id=user_id,
        kb_id=kb_id,
        original_filename="stub.pdf",
        storage_path="stub.pdf",
        file_type="pdf",
        file_size_bytes=1,
        status=DocumentStatus.UPLOADED,
    )
    session.add(document)
    await session.commit()
    return document.id


async def _stub_chunks(
    session: AsyncSession, *, document_id: int, indices: list[int], chunk_count: int | None = None
) -> None:
    """造片段。`indices` 允许乱序传入，以便验"返回按 chunk_index 升序"。"""
    for index in indices:
        session.add(
            Chunk(
                document_id=document_id,
                chunk_index=index,
                content=f"chunk-{index}",
                token_count=10 + index,
            )
        )
    document = await session.get(Document, document_id)
    document.chunk_count = chunk_count if chunk_count is not None else len(indices)
    await session.commit()


async def _soft_delete(session: AsyncSession, document_id: int) -> None:
    """写墓碑（9.1 才会实现接口，这里直接造状态来验读取路径）。"""
    document = await session.get(Document, document_id)
    document.deleted_at = datetime.now(timezone.utc)
    await session.commit()


# ---------------------------------------------------------------------------
# 5.1 上传受理
# ---------------------------------------------------------------------------


async def test_upload_accepted_returns_201_and_persists_everything(
    client, two_accounts, db_session, upload_root, monkeypatch
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "上传库")
    enqueued: list[int] = []
    monkeypatch.setattr(doc_service, "_default_enqueue", enqueued.append)

    resp = await _upload(client, alice, kb_id=kb_id)
    assert resp.status_code == 201, resp.text
    payload = resp.json()

    assert payload["kb_id"] == kb_id
    assert payload["status"] == "uploaded"
    assert payload["chunk_count"] == 0
    assert payload["file_type"] == "pdf"
    assert payload["file_size_bytes"] == len(PDF_BODY)
    assert payload["original_filename"] == "手册.pdf"
    assert payload["error_message"] is None
    # storage_path 是服务端内部字段，不该出现在对外视图里
    assert "storage_path" not in payload

    # 查库：归属由凭证决定、状态是 uploaded
    stored = await db_session.get(Document, payload["id"])
    assert stored.user_id == alice.id
    assert stored.status == DocumentStatus.UPLOADED

    # 落盘：文件真的存在，且内容与提交的一模一样
    on_disk = upload_root / stored.storage_path
    assert on_disk.exists(), f"落盘文件不存在：{on_disk}"
    assert on_disk.read_bytes() == PDF_BODY
    assert stored.storage_path != stored.original_filename  # 落盘名由服务端生成

    # 投递：恰好一次，且处理记录恰好一行
    assert enqueued == [payload["id"]]
    assert await _task_count(db_session, payload["id"]) == 1


@pytest.mark.parametrize("filename", ["notes.txt", "handbook.md", "spec.docx", "manual.pdf"])
async def test_all_four_supported_types_are_accepted(
    client, two_accounts, db_session, upload_root, filename
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, f"格式库-{filename}")
    body = b"content of " + filename.encode()

    resp = await _upload(client, alice, kb_id=kb_id, filename=filename, body=body)
    assert resp.status_code == 201, resp.text
    payload = resp.json()
    assert payload["file_type"] == filename.rsplit(".", 1)[1]

    # 四种格式是主路径，不能只看状态码：查库 + 查盘
    stored = await db_session.get(Document, payload["id"])
    assert stored.status == DocumentStatus.UPLOADED
    assert stored.file_size_bytes == len(body)
    assert (upload_root / stored.storage_path).read_bytes() == body


async def test_filename_longer_than_the_column_is_rejected(
    client, two_accounts, db_session, upload_root
):
    """`original_filename` 是 `VARCHAR(512)`：超长必须在接口层拒掉。

    不拒的话会以 `StringDataRightTruncation` 从数据库冒上来变成 500 —— 那正是
    1.6 的错误契约要挡住的"内部实现细节外泄"。
    """
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "长文件名库")
    before = await _count(db_session, Document)
    files_before = _files(upload_root)

    too_long = "n" * (ORIGINAL_FILENAME_MAX_LENGTH - 3) + ".pdf"
    assert len(too_long) == ORIGINAL_FILENAME_MAX_LENGTH + 1
    resp = await _upload(client, alice, kb_id=kb_id, filename=too_long)
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["code"] == "validation_error"
    assert str(ORIGINAL_FILENAME_MAX_LENGTH) in body["message"]
    assert await _count(db_session, Document) == before
    assert _files(upload_root) == files_before


async def test_filename_exactly_at_the_column_limit_is_accepted(
    client, two_accounts, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "文件名边界库")
    exact = "n" * (ORIGINAL_FILENAME_MAX_LENGTH - 4) + ".pdf"
    assert len(exact) == ORIGINAL_FILENAME_MAX_LENGTH
    resp = await _upload(client, alice, kb_id=kb_id, filename=exact)
    assert resp.status_code == 201, resp.text
    assert resp.json()["original_filename"] == exact


async def test_extension_matching_is_case_insensitive(
    client, two_accounts, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "大小写库")
    resp = await _upload(client, alice, kb_id=kb_id, filename="NOTES.PDF")
    assert resp.status_code == 201, resp.text
    assert resp.json()["file_type"] == "pdf"  # 入库值统一小写（与 allowed_extensions 同口径）


async def test_empty_file_is_accepted(client, two_accounts, upload_root):
    """0 字节文件**不在提交阶段被拒**：它是合法提交，能否处理出内容是 6.x 的事。"""
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "空文件库")
    resp = await _upload(client, alice, kb_id=kb_id, filename="empty.txt", body=b"")
    assert resp.status_code == 201, resp.text
    assert resp.json()["file_size_bytes"] == 0


async def test_unsupported_extension_is_rejected_without_any_trace(
    client, two_accounts, db_session, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "白名单库")
    before = await _count(db_session, Document)
    files_before = _files(upload_root)

    resp = await _upload(client, alice, kb_id=kb_id, filename="data.csv", body=b"a,b\n1,2\n")
    assert resp.status_code == 415, resp.text
    body = resp.json()
    assert body["code"] == "unsupported_media_type"
    assert "csv" in body["message"]
    assert body["detail"]["allowed_extensions"] == ["docx", "md", "pdf", "txt"]

    assert await _count(db_session, Document) == before, "被拒的提交不该产生文档记录"
    assert _files(upload_root) == files_before, "被拒的提交不该落盘"


async def test_filename_without_extension_is_rejected(
    client, two_accounts, db_session, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "无扩展名库")
    before = await _count(db_session, Document)
    resp = await _upload(client, alice, kb_id=kb_id, filename="README", body=b"text")
    assert resp.status_code == 415, resp.text
    assert "（无扩展名）" in resp.json()["message"]
    assert await _count(db_session, Document) == before


async def test_oversize_upload_is_rejected_before_anything_is_written(
    client, two_accounts, db_session, upload_root
):
    """`upload_root` 把上限压到 2MB，故 3MB 载荷即可覆盖"超限"这条路径。

    判据两条：不产生文档记录，且**一个字节都不落盘**（体积判定发生在落盘之前，
    所以这里是"从未创建"而不是"创建后又删掉"）。
    """
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "超限库")
    before = await _count(db_session, Document)
    files_before = _files(upload_root)

    resp = await _upload(
        client, alice, kb_id=kb_id, filename="big.pdf", body=b"x" * (3 * 1024 * 1024)
    )
    assert resp.status_code == 413, resp.text
    body = resp.json()
    assert body["code"] == "payload_too_large"
    assert "2MB" in body["message"]
    assert body["detail"]["max_upload_mb"] == 2

    assert await _count(db_session, Document) == before
    assert _files(upload_root) == files_before, "超限请求不该在共享卷上留下任何文件"


async def test_upload_exactly_at_the_size_limit_is_accepted(
    client, two_accounts, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "边界库")
    resp = await _upload(
        client, alice, kb_id=kb_id, filename="exact.pdf", body=b"x" * (2 * 1024 * 1024)
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["file_size_bytes"] == 2 * 1024 * 1024


async def test_streaming_size_guard_aborts_even_if_the_declared_size_lies(
    client, two_accounts, upload_root
):
    """权威闸门单测：直接喂一个"声称自己很小"的 UploadFile 给 `_stream_to_disk`。

    接口层的超限用例走的是 `store_upload` 开头那次 `upload.size` 快速闸门
    （不碰磁盘，见该函数的文档字符串）。这一条故意绕过它，证明**按实际落盘字节数**
    的那条闸门也是有效的 —— 上游声称的尺寸永远只是优化，不是保证。
    `_stream_to_disk` 是纯函数，不改库也不删文件，故不需要活动账号。
    """
    from starlette.datastructures import UploadFile as StarletteUploadFile

    from app.core.errors import PayloadTooLargeError

    declared_lies = StarletteUploadFile(
        file=io.BytesIO(b"x" * (3 * 1024 * 1024)), size=1, filename="liar.pdf"
    )
    destination = upload_root / "streamed.part"
    with pytest.raises(PayloadTooLargeError) as excinfo:
        await doc_service._stream_to_disk(
            declared_lies, destination, max_bytes=2 * 1024 * 1024, max_mb=2
        )
    assert "2MB" in str(excinfo.value)
    # 判据写成"写了、但从未越过上限"，不写成 `== 2MB`：
    # 现在的 1MB 块大小恰好让它在 2MB 上停住，但那是巧合而不是契约。
    # 真实不变式是"越界的那一块不会被写下去"，即落盘字节数永远 ≤ 上限。
    written = destination.stat().st_size
    assert 0 < written <= 2 * 1024 * 1024, f"落盘 {written} 字节，越过了上限"


async def test_missing_kb_id_is_rejected(client, two_accounts, db_session, upload_root):
    alice, _ = two_accounts
    before = await _count(db_session, Document)
    resp = await client.post(
        DOCS,
        files={"file": ("a.pdf", PDF_BODY, "application/octet-stream")},
        headers=alice.auth_header,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "validation_error"
    assert "kb_id" in str(resp.json()["detail"])
    assert await _count(db_session, Document) == before


async def test_missing_file_field_is_rejected(client, two_accounts, db_session, upload_root):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "缺文件库")
    before = await _count(db_session, Document)
    resp = await client.post(
        DOCS, data={"kb_id": str(kb_id)}, headers=alice.auth_header
    )
    assert resp.status_code == 422, resp.text
    assert "file" in str(resp.json()["detail"])
    assert await _count(db_session, Document) == before


async def test_non_numeric_kb_id_is_rejected(client, two_accounts, upload_root):
    alice, _ = two_accounts
    resp = await client.post(
        DOCS,
        files={"file": ("a.pdf", PDF_BODY, "application/octet-stream")},
        data={"kb_id": "not-a-number"},
        headers=alice.auth_header,
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 5.2 归属约束
# ---------------------------------------------------------------------------


async def test_upload_to_someone_elses_kb_is_404_without_side_effects(
    client, two_accounts, db_session, upload_root
):
    alice, bob = two_accounts
    alice_kb = await _create_kb(client, alice, "alice 的库")
    before = await _count(db_session, Document)
    files_before = _files(upload_root)

    resp = await _upload(client, bob, kb_id=alice_kb, filename="偷传.pdf")
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "not_found"

    assert await _count(db_session, Document) == before, "越权提交不该产生文档记录"
    assert _files(upload_root) == files_before, "越权提交不该在服务器上留下字节"


async def test_upload_to_a_nonexistent_kb_is_404(client, two_accounts, upload_root):
    alice, _ = two_accounts
    resp = await _upload(client, alice, kb_id=999_999, filename="x.pdf")
    assert resp.status_code == 404, resp.text


async def test_upload_ignores_user_id_in_the_request_body(
    client, two_accounts, db_session, upload_root
):
    """3.3 定的规矩在真正的越权写入口上再收口一次：归属只由凭证推导。"""
    alice, bob = two_accounts
    kb_id = await _create_kb(client, alice, "归属库")

    resp = await client.post(
        DOCS,
        files={"file": ("a.pdf", PDF_BODY, "application/octet-stream")},
        data={"kb_id": str(kb_id), "user_id": str(bob.id)},
        headers=alice.auth_header,
    )
    assert resp.status_code == 201, resp.text
    stored = await db_session.get(Document, resp.json()["id"])
    assert stored.user_id == alice.id, "请求体里的 user_id 必须被忽略"


async def test_upload_without_credentials_is_401_and_writes_nothing(
    client, two_accounts, db_session, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "未登录库")
    before = await _count(db_session, Document)
    files_before = _files(upload_root)
    resp = await client.post(
        DOCS,
        files={"file": ("a.pdf", PDF_BODY, "application/octet-stream")},
        data={"kb_id": str(kb_id)},
    )
    assert resp.status_code == 401, resp.text
    assert await _count(db_session, Document) == before
    assert _files(upload_root) == files_before


# ---------------------------------------------------------------------------
# 5.3 任务投递与并发保护
# ---------------------------------------------------------------------------


async def test_concurrent_dispatch_yields_exactly_one_processing_task(
    client, two_accounts, session_factory, db_session, redis_client, upload_root
):
    """并发投递同一文档：只产生一条处理记录，且只入队一次。

    两个协程各开**自己的**会话（`AsyncSession` 不是并发安全的，共用一个会串味）。
    """
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "并发库")
    document_id = await _stub_document(db_session, user_id=alice.id, kb_id=kb_id)
    enqueued: list[int] = []

    async def _dispatch() -> bool:
        async with session_factory() as session:
            return await doc_service.dispatch_processing_task(
                session, redis_client, document_id=document_id, enqueue=enqueued.append
            )

    results = await asyncio.gather(_dispatch(), _dispatch())

    assert results.count(True) == 1, f"应恰好有一次真的投递，实际 {results}"
    assert enqueued == [document_id], f"入队次数应为 1，实际 {enqueued}"
    assert await _task_count(db_session, document_id) == 1


async def test_dispatch_is_skipped_while_the_lock_is_held(
    client, two_accounts, db_session, redis_client, upload_root
):
    """锁真的在挡事：预先占住锁 → 本次投递什么都不做（而不是照常插入 + 入队）。"""
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "占锁库")
    document_id = await _stub_document(db_session, user_id=alice.id, kb_id=kb_id)
    key = f"{doc_service.DISPATCH_LOCK_KEY_PREFIX}{document_id}"
    await redis_client.set(key, "another-dispatcher", nx=True, px=10_000)

    enqueued: list[int] = []
    dispatched = await doc_service.dispatch_processing_task(
        db_session, redis_client, document_id=document_id, enqueue=enqueued.append
    )

    assert dispatched is False
    assert enqueued == []
    assert await _task_count(db_session, document_id) == 0


async def test_lock_is_released_after_dispatch(
    client, two_accounts, db_session, redis_client, upload_root
):
    """临界区结束必须放锁，否则该文档此后再也无法投递（TTL 到期前）。"""
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "放锁库")
    document_id = await _stub_document(db_session, user_id=alice.id, kb_id=kb_id)
    key = f"{doc_service.DISPATCH_LOCK_KEY_PREFIX}{document_id}"

    dispatched = await doc_service.dispatch_processing_task(
        db_session, redis_client, document_id=document_id, enqueue=lambda _: None
    )
    assert dispatched is True
    assert await redis_client.get(key) is None, "投递完成后锁必须已被释放"


async def test_second_dispatch_of_the_same_document_is_a_noop(
    client, two_accounts, db_session, redis_client, upload_root
):
    """重复投递（不并发）也只入队一次 —— 靠的是唯一约束，不只是锁。"""
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "重复投递库")
    document_id = await _stub_document(db_session, user_id=alice.id, kb_id=kb_id)
    enqueued: list[int] = []

    first = await doc_service.dispatch_processing_task(
        db_session, redis_client, document_id=document_id, enqueue=enqueued.append
    )
    second = await doc_service.dispatch_processing_task(
        db_session, redis_client, document_id=document_id, enqueue=enqueued.append
    )

    assert (first, second) == (True, False)
    assert enqueued == [document_id]
    assert await _task_count(db_session, document_id) == 1


async def test_ensure_processing_task_reports_only_the_first_insert(
    client, two_accounts, db_session, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "幂等库")
    document_id = await _stub_document(db_session, user_id=alice.id, kb_id=kb_id)

    assert await doc_service.ensure_processing_task(db_session, document_id=document_id) is True
    assert await doc_service.ensure_processing_task(db_session, document_id=document_id) is False
    assert await _task_count(db_session, document_id) == 1


async def test_processing_tasks_document_id_unique_constraint_is_real(
    client, two_accounts, db_session, upload_root
):
    """绕过 service 直接插两行 → 必须被唯一约束拦下（这是 5.3 的最终裁判）。"""
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "唯一约束库")
    document_id = await _stub_document(db_session, user_id=alice.id, kb_id=kb_id)

    db_session.add(ProcessingTask(document_id=document_id))
    await db_session.commit()
    db_session.add(ProcessingTask(document_id=document_id))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
    assert await _task_count(db_session, document_id) == 1


async def test_dispatch_commits_before_enqueueing(redis_client):
    """**顺序不能反**：worker 是另一个进程，看不到未提交的行。

    这条约束没法用真并发稳定观测（故障窗口是"投递成功但事务未提交"），所以用一个
    记录调用次序的假会话把它钉死：先 INSERT 处理记录 → commit → 才 enqueue。
    订正它的人会立刻看到这条断言变红，而不是等到线上出现"文档不存在"的偶发失败。
    """

    calls: list[str] = []

    class _RecordingSession:
        async def scalar(self, _statement):
            calls.append("insert_processing_task")
            return 1  # 假装 INSERT ... RETURNING 带回了新 id（= 本次是第一个投递者）

        async def commit(self):
            calls.append("commit")

    dispatched = await doc_service.dispatch_processing_task(
        _RecordingSession(),  # type: ignore[arg-type]
        redis_client,
        document_id=1,
        enqueue=lambda _: calls.append("enqueue"),
    )

    assert dispatched is True
    assert calls == ["insert_processing_task", "commit", "enqueue"]


async def test_chunk_query_carries_its_own_ownership_filter(
    client, two_accounts, db_session, upload_root
):
    """`list_chunks` 自带归属过滤（JOIN 文档）：传错 `user_id` 就查不到。

    D-038 定下的口径是"归属前提不该靠读代码的人记得上面查过"，
    所以这一层必须自己挡得住 —— 绕过路由直接调 service 也一样。
    """
    alice, bob = two_accounts
    kb_id = await _create_kb(client, alice, "自带过滤库")
    document_id = (await _upload(client, alice, kb_id=kb_id)).json()["id"]
    await _stub_chunks(db_session, document_id=document_id, indices=[0, 1])

    mine = await doc_service.list_chunks(
        db_session, user_id=alice.id, document_id=document_id
    )
    theirs = await doc_service.list_chunks(
        db_session, user_id=bob.id, document_id=document_id
    )
    assert [chunk.chunk_index for chunk in mine] == [0, 1]
    assert list(theirs) == [], "换一个 user_id 就不该查到别人的片段"


# ---------------------------------------------------------------------------
# 5.4 片段反查
# ---------------------------------------------------------------------------


async def test_chunks_are_returned_in_order_and_match_chunk_count(
    client, two_accounts, db_session, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "片段库")
    document_id = (await _upload(client, alice, kb_id=kb_id)).json()["id"]
    # 乱序插入，验证返回是按 chunk_index 升序而不是插入顺序
    await _stub_chunks(db_session, document_id=document_id, indices=[2, 0, 1], chunk_count=3)

    resp = await client.get(f"{DOCS}/{document_id}/chunks", headers=alice.auth_header)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert [chunk["chunk_index"] for chunk in payload] == [0, 1, 2]
    assert payload[0]["content"] == "chunk-0"
    assert payload[0]["token_count"] == 10
    assert set(payload[0]) == {"chunk_index", "content", "token_count"}

    detail = (await client.get(f"{DOCS}/{document_id}", headers=alice.auth_header)).json()
    assert len(payload) == detail["chunk_count"] == 3, "片段总数必须与文档 chunk_count 一致"


async def test_chunks_of_a_document_without_chunks_is_an_empty_list(
    client, two_accounts, db_session, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "无片段库")
    document_id = (await _upload(client, alice, kb_id=kb_id)).json()["id"]

    resp = await client.get(f"{DOCS}/{document_id}/chunks", headers=alice.auth_header)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_chunks_of_someone_elses_document_is_404(
    client, two_accounts, db_session, upload_root
):
    alice, bob = two_accounts
    kb_id = await _create_kb(client, alice, "越权片段库")
    document_id = (await _upload(client, alice, kb_id=kb_id)).json()["id"]
    await _stub_chunks(db_session, document_id=document_id, indices=[0])

    resp = await client.get(f"{DOCS}/{document_id}/chunks", headers=bob.auth_header)
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "not_found"


async def test_chunks_of_a_deleted_document_is_404(
    client, two_accounts, db_session, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "墓碑片段库")
    document_id = (await _upload(client, alice, kb_id=kb_id)).json()["id"]
    await _stub_chunks(db_session, document_id=document_id, indices=[0])
    await _soft_delete(db_session, document_id)

    resp = await client.get(f"{DOCS}/{document_id}/chunks", headers=alice.auth_header)
    assert resp.status_code == 404, resp.text


async def test_chunks_require_credentials(client, two_accounts, db_session, upload_root):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "凭据片段库")
    document_id = (await _upload(client, alice, kb_id=kb_id)).json()["id"]
    resp = await client.get(f"{DOCS}/{document_id}/chunks")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 5.5 列表与详情
# ---------------------------------------------------------------------------


async def test_list_returns_only_own_documents(
    client, two_accounts, db_session, upload_root
):
    alice, bob = two_accounts
    alice_kb = await _create_kb(client, alice, "alice 列表库")
    bob_kb = await _create_kb(client, bob, "bob 列表库")
    alice_ids = [
        (await _upload(client, alice, kb_id=alice_kb, filename=f"a{i}.pdf", body=PDF_BODY + bytes([i]))).json()["id"]
        for i in range(2)
    ]
    bob_id = (await _upload(client, bob, kb_id=bob_kb, filename="b.pdf")).json()["id"]

    payload = (await client.get(DOCS, headers=alice.auth_header)).json()
    listed = {item["id"] for item in payload}
    assert listed == set(alice_ids)
    assert bob_id not in listed

    # 列表条目带齐 5.5 要求的字段
    first = payload[0]
    assert {"kb_id", "status", "chunk_count", "original_filename", "file_size_bytes"} <= set(first)
    assert first["status"] == "uploaded"


async def test_list_filters_by_kb_without_crossing_libraries(
    client, two_accounts, upload_root
):
    alice, _ = two_accounts
    kb_a = await _create_kb(client, alice, "库 A")
    kb_b = await _create_kb(client, alice, "库 B")
    in_a = [
        (await _upload(client, alice, kb_id=kb_a, filename=f"a{i}.txt")).json()["id"]
        for i in range(2)
    ]
    in_b = [(await _upload(client, alice, kb_id=kb_b, filename="b0.txt")).json()["id"]]

    payload = (await client.get(f"{DOCS}?kb_id={kb_a}", headers=alice.auth_header)).json()
    assert {item["id"] for item in payload} == set(in_a)
    assert all(item["kb_id"] == kb_a for item in payload)

    payload_b = (await client.get(f"{DOCS}?kb_id={kb_b}", headers=alice.auth_header)).json()
    assert {item["id"] for item in payload_b} == set(in_b)


async def test_list_filtered_by_someone_elses_kb_is_404(
    client, two_accounts, upload_root
):
    alice, bob = two_accounts
    alice_kb = await _create_kb(client, alice, "被筛的库")
    await _upload(client, alice, kb_id=alice_kb, filename="a.pdf")

    resp = await client.get(f"{DOCS}?kb_id={alice_kb}", headers=bob.auth_header)
    assert resp.status_code == 404, resp.text


async def test_list_excludes_tombstoned_documents(
    client, two_accounts, db_session, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "墓碑列表库")
    live_id = (await _upload(client, alice, kb_id=kb_id, filename="live.pdf")).json()["id"]
    dead_id = (await _upload(client, alice, kb_id=kb_id, filename="dead.pdf")).json()["id"]
    await _soft_delete(db_session, dead_id)

    payload = (await client.get(DOCS, headers=alice.auth_header)).json()
    listed = {item["id"] for item in payload}
    assert live_id in listed
    assert dead_id not in listed, "读取路径一律要带 deleted_at IS NULL（D-024）"


async def test_get_detail_returns_expected_fields(
    client, two_accounts, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "详情库")
    created = (await _upload(client, alice, kb_id=kb_id)).json()

    resp = await client.get(f"{DOCS}/{created['id']}", headers=alice.auth_header)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["id"] == created["id"]
    assert payload["kb_id"] == kb_id
    assert payload["original_filename"] == "手册.pdf"
    assert payload["file_type"] == "pdf"
    assert payload["file_size_bytes"] == len(PDF_BODY)
    assert payload["status"] == "uploaded"
    assert payload["chunk_count"] == 0
    assert payload["error_message"] is None


async def test_get_detail_of_someone_elses_document_is_404(
    client, two_accounts, upload_root
):
    alice, bob = two_accounts
    kb_id = await _create_kb(client, alice, "越权详情库")
    document_id = (await _upload(client, alice, kb_id=kb_id)).json()["id"]

    resp = await client.get(f"{DOCS}/{document_id}", headers=bob.auth_header)
    assert resp.status_code == 404, resp.text


async def test_get_detail_of_a_deleted_document_is_404(
    client, two_accounts, db_session, upload_root
):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "墓碑详情库")
    document_id = (await _upload(client, alice, kb_id=kb_id)).json()["id"]
    await _soft_delete(db_session, document_id)

    resp = await client.get(f"{DOCS}/{document_id}", headers=alice.auth_header)
    assert resp.status_code == 404, resp.text


async def test_get_detail_of_a_nonexistent_document_is_404(client, two_accounts):
    alice, _ = two_accounts
    resp = await client.get(f"{DOCS}/999999", headers=alice.auth_header)
    assert resp.status_code == 404, resp.text


async def test_all_document_reads_require_credentials(client, two_accounts, upload_root):
    alice, _ = two_accounts
    kb_id = await _create_kb(client, alice, "凭据库")
    document_id = (await _upload(client, alice, kb_id=kb_id)).json()["id"]

    assert (await client.get(DOCS)).status_code == 401
    assert (await client.get(f"{DOCS}/{document_id}")).status_code == 401
    assert (await client.get(f"{DOCS}/{document_id}/chunks")).status_code == 401
    assert (
        await client.post(
            DOCS,
            files={"file": ("a.pdf", PDF_BODY, "application/octet-stream")},
            data={"kb_id": str(kb_id)},
        )
    ).status_code == 401
