"""任务 4.1 / 4.2 的接口层验收。

判据来源：
- `openspec/changes/add-doc-ingest-pipeline/specs/knowledge-base/spec.md`
  （创建知识库 / 知识库列表 / 重命名知识库 / 删除知识库）
- `tasks.md` 4.1 / 4.2 的"验证"行
- `docs/findings.md` D-024 的衔接点：文档数量与非空判断**只算 `deleted_at IS NULL`**，
  只剩墓碑行的库要能删掉（先物理清墓碑，否则被 RESTRICT 外键拦住）

**关于造数据**：5.x 的上传接口尚未实现，所以"库里有文档"这一步只能直接插 `documents` 行。
这不是绕过被测代码——被测的是 4.x 的"计数 / 拒删"逻辑，不是"文档怎么来的"；
5.x 落地后这些用例仍成立（届时可换成走上传接口）。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# 名称上限取自 DDL（knowledge_bases.name VARCHAR(128)），不写死字面量
from app.models.knowledge_base import KB_NAME_MAX_LENGTH

KBS = "/api/knowledge-bases"


# --------------------------------------------------------------------------- 工具


async def _scalar(db_engine, sql: str, **params):
    async with db_engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar_one()


async def _row(db_engine, sql: str, **params):
    async with db_engine.connect() as conn:
        return (await conn.execute(text(sql), params)).mappings().one()


async def _create_kb(client, account, name: str, description: str | None = None) -> int:
    body: dict[str, object] = {"name": name}
    if description is not None:
        body["description"] = description
    resp = await client.post(KBS, json=body, headers=account.auth_header)
    assert resp.status_code == 201, f"建库失败：{resp.status_code} {resp.text}"
    return resp.json()["id"]


async def _insert_document(
    db_engine, *, kb_id: int, user_id: int, filename: str = "a.pdf", deleted: bool = False
) -> int:
    """造一条文档行。`deleted=True` 时写墓碑（`deleted_at` 非空）。"""
    async with db_engine.begin() as conn:
        return (
            await conn.execute(
                text(
                    """
                    INSERT INTO documents
                        (user_id, kb_id, original_filename, storage_path, file_type,
                         file_size_bytes, status, deleted_at)
                    VALUES (:user_id, :kb_id, :filename, 'uploads/stub.pdf', 'pdf',
                            1024, 'ready', :deleted_at)
                    RETURNING id
                    """
                ),
                {
                    "user_id": user_id,
                    "kb_id": kb_id,
                    "filename": filename,
                    "deleted_at": datetime.now(UTC) if deleted else None,
                },
            )
        ).scalar_one()


# ----------------------------------------------------------------- 4.1 创建知识库


async def test_create_knowledge_base(client, db_schema, db_engine, account_factory):
    alice = await account_factory("alice")

    resp = await client.post(
        KBS, json={"name": "面试八股", "description": "复习用"}, headers=alice.auth_header
    )
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["name"] == "面试八股"
    assert body["description"] == "复习用"
    assert body["document_count"] == 0
    assert isinstance(body["id"], int) and body["created_at"]

    # 规格：该知识库随即出现在该用户的知识库列表中（以查库为准，不只看 201）
    assert await _scalar(
        db_engine, "SELECT user_id FROM knowledge_bases WHERE id = :id", id=body["id"]
    ) == alice.id

    listed = await client.get(KBS, headers=alice.auth_header)
    assert [item["id"] for item in listed.json()] == [body["id"]]


async def test_create_trims_surrounding_whitespace(client, db_schema, account_factory):
    alice = await account_factory("alice")
    resp = await client.post(KBS, json={"name": "  知识库  "}, headers=alice.auth_header)
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "知识库"

    # 归一化之后重名照样该拦
    again = await client.post(KBS, json={"name": "知识库"}, headers=alice.auth_header)
    assert again.status_code == 409


async def test_create_accepts_name_exactly_at_the_upper_bound(
    client, db_schema, account_factory
):
    """边界：恰好 128 字符必须通过——差一位都不该提前失败。"""
    alice = await account_factory("alice")
    name = "库" * KB_NAME_MAX_LENGTH
    resp = await client.post(KBS, json={"name": name}, headers=alice.auth_header)
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == name


async def test_create_accepts_padded_name_that_fits_after_trimming(
    client, db_schema, account_factory
):
    """两端空白先去掉再判长度：`"  " + 128 字` 归一化后恰好合法，不该被误杀。

    这条锁住的是校验顺序（`mode="before"` 先 strip 再判长）。若换成
    `Field(max_length=128)` 先判原始串，本用例会变红。
    """
    alice = await account_factory("alice")
    resp = await client.post(
        KBS, json={"name": "  " + "库" * KB_NAME_MAX_LENGTH}, headers=alice.auth_header
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "库" * KB_NAME_MAX_LENGTH


@pytest.mark.parametrize(
    ("name", "expected_hint"),
    [
        ("", "不能为空"),
        ("   ", "不能为空"),
        ("\t\n", "不能为空"),
        ("库" * (KB_NAME_MAX_LENGTH + 1), "长度不超过 128 个字符"),
    ],
)
async def test_create_rejects_blank_or_too_long_name(
    client, db_schema, db_engine, account_factory, name, expected_hint
):
    alice = await account_factory("alice")
    resp = await client.post(KBS, json={"name": name}, headers=alice.auth_header)

    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "validation_error"
    # 规格要求"说明名称限制"，不能只回一句"参数不合法"
    assert expected_hint in json.dumps(resp.json(), ensure_ascii=False)

    assert await _scalar(db_engine, "SELECT count(*) FROM knowledge_bases") == 0


async def test_create_rejects_missing_name(client, db_schema, account_factory):
    """`name` 整个字段都不给 → 422，且 detail 里点名是哪个字段缺了。"""
    alice = await account_factory("alice")
    resp = await client.post(KBS, json={}, headers=alice.auth_header)
    assert resp.status_code == 422
    detail = json.dumps(resp.json()["detail"], ensure_ascii=False)
    assert "name" in detail, detail


async def test_create_duplicate_name_in_the_same_account_is_rejected(
    client, db_schema, db_engine, account_factory
):
    alice = await account_factory("alice")
    await _create_kb(client, alice, "重名的库")

    again = await client.post(KBS, json={"name": "重名的库"}, headers=alice.auth_header)
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "conflict"

    assert await _scalar(db_engine, "SELECT count(*) FROM knowledge_bases") == 1


async def test_same_name_is_allowed_across_accounts(client, db_schema, two_accounts):
    """唯一性范围是"同一账号下"（`uq_kb_user_name` 是 (user_id, name) 复合索引）。"""
    alice, bob = two_accounts
    assert (
        await client.post(KBS, json={"name": "重名的库"}, headers=alice.auth_header)
    ).status_code == 201
    assert (
        await client.post(KBS, json={"name": "重名的库"}, headers=bob.auth_header)
    ).status_code == 201


async def test_create_ignores_user_id_in_the_request_body(
    client, db_schema, db_engine, two_accounts
):
    """3.3 的 defer 在这里收口：越权**写**操作真的落到了正确的账号。

    请求体里塞 `user_id = bob.id`，建出来的库必须归 alice —— 归属只由凭证推导。
    """
    alice, bob = two_accounts

    resp = await client.post(
        KBS,
        json={"name": "伪装成 bob 的库", "user_id": bob.id},
        headers=alice.auth_header,
    )
    assert resp.status_code == 201, resp.text

    kb_id = resp.json()["id"]
    assert await _scalar(
        db_engine, "SELECT user_id FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == alice.id, "请求体里的 user_id 不得影响归属"

    # bob 的列表里不该出现它
    assert (await client.get(KBS, headers=bob.auth_header)).json() == []


async def test_create_requires_authentication(client, db_schema):
    resp = await client.post(KBS, json={"name": "未登录建的库"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"


# ----------------------------------------------------------------- 4.1 知识库列表


async def test_list_only_contains_own_knowledge_bases(client, db_schema, two_accounts):
    """规格「列表只含自己的知识库」：双账号交叉验。"""
    alice, bob = two_accounts
    await _create_kb(client, alice, "alice 的库")
    await _create_kb(client, bob, "bob 的库")
    await _create_kb(client, bob, "bob 的第二个库")

    alice_list = (await client.get(KBS, headers=alice.auth_header)).json()
    bob_list = (await client.get(KBS, headers=bob.auth_header)).json()

    assert [item["name"] for item in alice_list] == ["alice 的库"]
    # 顺带锁住列表顺序：按创建先后返回（created_at, id 升序），不依赖 PG 的返回顺序
    assert [item["name"] for item in bob_list] == ["bob 的库", "bob 的第二个库"]


async def test_list_includes_document_count_excluding_tombstones(
    client, db_schema, db_engine, account_factory
):
    """规格「列表包含文档数量」+ D-024 衔接点：墓碑行**不**计入。"""
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "有文档的库")
    empty_kb_id = await _create_kb(client, alice, "空库")

    await _insert_document(db_engine, kb_id=kb_id, user_id=alice.id, filename="a.pdf")
    await _insert_document(db_engine, kb_id=kb_id, user_id=alice.id, filename="b.pdf")
    # 墓碑：已删除的文档，不得计入
    await _insert_document(
        db_engine, kb_id=kb_id, user_id=alice.id, filename="gone.pdf", deleted=True
    )

    listed = {item["id"]: item for item in (await client.get(KBS, headers=alice.auth_header)).json()}
    assert listed[kb_id]["document_count"] == 2, "墓碑行被算进了文档数量"
    assert listed[empty_kb_id]["document_count"] == 0


async def test_list_requires_authentication(client, db_schema):
    assert (await client.get(KBS)).status_code == 401


# ------------------------------------------------------------------- 4.1 重命名


async def test_rename_takes_effect(client, db_schema, db_engine, account_factory):
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "旧名字", description="原简介")

    resp = await client.patch(
        f"{KBS}/{kb_id}", json={"name": "新名字"}, headers=alice.auth_header
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "新名字"

    # 列表随之变化（规格「列表与筛选结果随之变化」）
    listed = (await client.get(KBS, headers=alice.auth_header)).json()
    assert [item["name"] for item in listed] == ["新名字"]
    assert await _scalar(
        db_engine, "SELECT name FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == "新名字"


async def test_rename_without_description_keeps_the_existing_one(
    client, db_schema, db_engine, account_factory
):
    """PATCH 语义：只改名不该顺手把简介清空（`model_fields_set` 的用途）。

    PATCH 是写操作，判据以**查库**为准 —— 光看响应体的话，"响应里带着原简介、
    库里已被清空"这种实现也能骗过断言。
    """
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "旧名字", description="原简介")

    resp = await client.patch(
        f"{KBS}/{kb_id}", json={"name": "新名字"}, headers=alice.auth_header
    )
    assert resp.json()["description"] == "原简介"

    row = await _row(db_engine, "SELECT name, description FROM knowledge_bases WHERE id = :id", id=kb_id)
    assert row["name"] == "新名字"
    assert row["description"] == "原简介", "库里被清空了 —— 这就是那条静默的数据丢失"


async def test_rename_can_clear_description_explicitly(
    client, db_schema, db_engine, account_factory
):
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "旧名字", description="原简介")

    resp = await client.patch(
        f"{KBS}/{kb_id}",
        json={"name": "新名字", "description": None},
        headers=alice.auth_header,
    )
    assert resp.json()["description"] is None
    assert await _scalar(
        db_engine, "SELECT description IS NULL FROM knowledge_bases WHERE id = :id", id=kb_id
    ), "显式传 null 必须真的写进库里"


async def test_rename_to_its_own_name_is_allowed(
    client, db_schema, db_engine, account_factory
):
    """幂等：把 A 改成 A 不该报 409（重名检查必须排除自己）。"""
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "同一个名字")

    resp = await client.patch(
        f"{KBS}/{kb_id}", json={"name": "同一个名字"}, headers=alice.auth_header
    )
    assert resp.status_code == 200, resp.text
    assert await _scalar(
        db_engine, "SELECT name FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == "同一个名字"


async def test_rename_to_an_existing_name_is_rejected_and_data_unchanged(
    client, db_schema, db_engine, account_factory
):
    alice = await account_factory("alice")
    first = await _create_kb(client, alice, "库一")
    second = await _create_kb(client, alice, "库二")

    resp = await client.patch(
        f"{KBS}/{second}", json={"name": "库一"}, headers=alice.auth_header
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "conflict"

    assert await _scalar(
        db_engine, "SELECT name FROM knowledge_bases WHERE id = :id", id=second
    ) == "库二", "拒绝之后数据必须保持原样"
    assert await _scalar(
        db_engine, "SELECT name FROM knowledge_bases WHERE id = :id", id=first
    ) == "库一"


async def test_rename_other_users_knowledge_base_is_rejected_and_data_unchanged(
    client, db_schema, db_engine, two_accounts
):
    """规格「重命名他人知识库」：拒绝 + 数据不变。

    返回 404 而不是 403：403 等于确认"这个 id 真实存在，只是不属于你"，
    把他人资源的存在性变成了可探测信息。
    """
    alice, bob = two_accounts
    kb_id = await _create_kb(client, alice, "alice 的库")

    resp = await client.patch(
        f"{KBS}/{kb_id}", json={"name": "被 bob 改掉的库"}, headers=bob.auth_header
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "not_found"

    assert await _scalar(
        db_engine, "SELECT name FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == "alice 的库", "越权重命名不得修改任何数据"
    assert await _scalar(db_engine, "SELECT count(*) FROM knowledge_bases") == 1


async def test_rename_missing_knowledge_base_returns_404(client, db_schema, account_factory):
    alice = await account_factory("alice")
    resp = await client.patch(
        f"{KBS}/999999", json={"name": "随便"}, headers=alice.auth_header
    )
    assert resp.status_code == 404


@pytest.mark.parametrize(
    ("name", "expected_hint"),
    [
        ("", "不能为空"),
        ("   ", "不能为空"),
        ("库" * (KB_NAME_MAX_LENGTH + 1), "长度不超过 128 个字符"),
    ],
)
async def test_rename_applies_the_same_name_rules_as_create(
    client, db_schema, db_engine, account_factory, name, expected_hint
):
    """规格「重命名 MUST 遵守与创建相同的名称规则」——连"点名原因"这一半也一样。"""
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "旧名字")

    resp = await client.patch(f"{KBS}/{kb_id}", json={"name": name}, headers=alice.auth_header)
    assert resp.status_code == 422, resp.text
    assert expected_hint in json.dumps(resp.json(), ensure_ascii=False), resp.text

    # 被拒之后名字必须原封不动
    assert await _scalar(
        db_engine, "SELECT name FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == "旧名字"


async def test_rename_requires_authentication(client, db_schema, account_factory):
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "库")
    assert (await client.patch(f"{KBS}/{kb_id}", json={"name": "新名"})).status_code == 401


# --------------------------------------------------------------------- 4.2 删除


async def test_delete_empty_knowledge_base(client, db_schema, db_engine, account_factory):
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "空库")

    resp = await client.delete(f"{KBS}/{kb_id}", headers=alice.auth_header)
    assert resp.status_code == 204, resp.text
    assert resp.content == b""

    # 规格：删除成功，该知识库不再出现在列表中（以查库为准）
    assert (await client.get(KBS, headers=alice.auth_header)).json() == []
    assert await _scalar(
        db_engine, "SELECT count(*) FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == 0


async def test_delete_non_empty_knowledge_base_is_rejected_with_the_count(
    client, db_schema, db_engine, account_factory
):
    """规格「删除非空知识库被拒绝」：拒绝 + 给出**未被清空的文档数量**。"""
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "有文档的库")
    await _insert_document(db_engine, kb_id=kb_id, user_id=alice.id, filename="a.pdf")
    await _insert_document(db_engine, kb_id=kb_id, user_id=alice.id, filename="b.pdf")

    resp = await client.delete(f"{KBS}/{kb_id}", headers=alice.auth_header)
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["code"] == "conflict"
    assert body["detail"]["document_count"] == 2, body
    assert "2" in body["message"]

    # 库与文档都必须完好
    assert await _scalar(
        db_engine, "SELECT count(*) FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == 1
    assert await _scalar(
        db_engine, "SELECT count(*) FROM documents WHERE kb_id = :id", id=kb_id
    ) == 2


async def test_tombstoned_documents_do_not_block_deletion(
    client, db_schema, db_engine, account_factory
):
    """D-024 衔接点：库只剩墓碑行时**必须能删掉**。

    墓碑行仍持有 `kb_id`，而 `fk_documents_kb_id_knowledge_bases` 是不级联的 RESTRICT——
    所以 service 必须先物理清除墓碑再删库。少了那一步，本用例会被外键拦住（500）。
    """
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "只剩墓碑的库")
    await _insert_document(
        db_engine, kb_id=kb_id, user_id=alice.id, filename="gone.pdf", deleted=True
    )

    resp = await client.delete(f"{KBS}/{kb_id}", headers=alice.auth_header)
    assert resp.status_code == 204, resp.text

    assert await _scalar(
        db_engine, "SELECT count(*) FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == 0
    assert await _scalar(
        db_engine, "SELECT count(*) FROM documents WHERE kb_id = :id", id=kb_id
    ) == 0, "墓碑行应随库一并物理清除"


async def test_delete_race_with_a_concurrent_insert_is_refused(
    client, db_schema, db_engine, account_factory, monkeypatch
):
    """并发窗口的兜底：计数说"空"、库里其实已有在册文档时，**绝不能删成功**。

    真并发没法稳定复现，故用 monkeypatch 把计数函数钉成 0 来制造这个窗口。
    这条同时锁住"墓碑清除只删墓碑行"这句实现 —— 若写成"删该库全部文档"，
    本用例会返回 204 并把那份刚上传的文档**静默删掉**（比报错严重得多）。
    """
    from app.services import knowledge_base as kb_service

    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "竞态库")
    doc_id = await _insert_document(db_engine, kb_id=kb_id, user_id=alice.id)

    async def _pretend_empty(session, *, user_id, kb_id):
        return 0

    monkeypatch.setattr(kb_service, "count_live_documents", _pretend_empty)

    resp = await client.delete(f"{KBS}/{kb_id}", headers=alice.auth_header)
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "conflict"

    # 库与那份文档都必须还在
    assert await _scalar(
        db_engine, "SELECT count(*) FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == 1
    assert await _scalar(
        db_engine, "SELECT count(*) FROM documents WHERE id = :id", id=doc_id
    ) == 1, "并发落进来的在册文档被静默删掉了"


async def test_live_documents_block_deletion_at_the_database_level_too(
    client, db_schema, db_engine, account_factory
):
    """机制层断言：RESTRICT 外键真的在（应用层的检查只是第一道闸门）。

    绕过接口直接 DELETE 知识库行，必须被 `fk_documents_kb_id_knowledge_bases` 拦下——
    这条约束保证任何"漏写计数检查"的新代码路径也删不掉有文档的库。
    """
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "有文档的库")
    await _insert_document(db_engine, kb_id=kb_id, user_id=alice.id)

    with pytest.raises(IntegrityError):
        async with db_engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM knowledge_bases WHERE id = :id"), {"id": kb_id}
            )


async def test_delete_other_users_knowledge_base_is_rejected(
    client, db_schema, db_engine, two_accounts
):
    alice, bob = two_accounts
    kb_id = await _create_kb(client, alice, "alice 的库")

    resp = await client.delete(f"{KBS}/{kb_id}", headers=bob.auth_header)
    assert resp.status_code == 404, resp.text
    assert await _scalar(
        db_engine, "SELECT count(*) FROM knowledge_bases WHERE id = :id", id=kb_id
    ) == 1, "越权删除不得改动数据"


async def test_delete_missing_knowledge_base_returns_404(client, db_schema, account_factory):
    alice = await account_factory("alice")
    assert (await client.delete(f"{KBS}/999999", headers=alice.auth_header)).status_code == 404


async def test_delete_requires_authentication(client, db_schema, account_factory):
    alice = await account_factory("alice")
    kb_id = await _create_kb(client, alice, "库")
    assert (await client.delete(f"{KBS}/{kb_id}")).status_code == 401
    # 未登录的删除不得生效
    assert (await client.get(KBS, headers=alice.auth_header)).json() != []
