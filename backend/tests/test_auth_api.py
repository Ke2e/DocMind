"""任务 3.1 / 3.2 / 3.3 的接口层验收。

判据来源：
- `openspec/changes/add-doc-ingest-pipeline/specs/user-auth/spec.md` 的三个 Requirement
  （账号注册 / 登录与登录态 / 数据归属由登录态决定）
- 开发者 2026-09-12 拍板：密码强度 = ≥PASSWORD_MIN_LENGTH 且同时含字母与数字；双账号越权用例
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.deps import get_current_user
from app.main import create_app
from app.models import User

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
ME = "/api/auth/me"
STRONG = "docmind123"


# --------------------------------------------------------------------------- 3.1 注册


async def test_register_success(client, db_schema, db_engine):
    resp = await client.post(REGISTER, json={"username": "alice", "password": STRONG})
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["username"] == "alice"
    assert isinstance(body["id"], int)
    # 规格：响应中不包含密码或其摘要
    assert set(body) == {"id", "username"}
    assert STRONG not in resp.text

    async with db_engine.connect() as conn:
        rows = (await conn.execute(text("SELECT username, password_hash FROM users"))).mappings().all()
    assert len(rows) == 1
    assert rows[0]["password_hash"].startswith("$argon2id$")
    assert STRONG not in rows[0]["password_hash"]


async def test_register_duplicate_username_is_rejected(client, db_schema, db_engine):
    assert (
        await client.post(REGISTER, json={"username": "alice", "password": STRONG})
    ).status_code == 201

    again = await client.post(REGISTER, json={"username": "alice", "password": "another123"})
    assert again.status_code == 409, again.text
    assert again.json()["code"] == "conflict"

    async with db_engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM users"))).scalar_one() == 1, (
            "重复注册不得产生新账号"
        )


async def test_register_trims_surrounding_whitespace(client, db_schema):
    """两端空白不构成新名字：'  alice  ' 与 'alice' 是同一个账号。"""
    first = await client.post(REGISTER, json={"username": "  alice  ", "password": STRONG})
    assert first.status_code == 201, first.text
    assert first.json()["username"] == "alice"

    duplicate = await client.post(REGISTER, json={"username": "alice", "password": STRONG})
    assert duplicate.status_code == 409


async def test_register_is_case_sensitive_on_username(client, db_schema):
    """规格「用户名区分大小写」：`alice` 与 `Alice` 是两个互不影响的账号。"""
    assert (
        await client.post(REGISTER, json={"username": "alice", "password": STRONG})
    ).status_code == 201
    second = await client.post(REGISTER, json={"username": "Alice", "password": STRONG})
    assert second.status_code == 201, second.text
    assert second.json()["username"] == "Alice"

    # 两个账号各自能登录，且身份不同
    tokens = []
    for name in ("alice", "Alice"):
        resp = await client.post(LOGIN, json={"username": name, "password": STRONG})
        assert resp.status_code == 200, resp.text
        tokens.append(resp.json()["access_token"])

    identities = []
    for token in tokens:
        resp = await client.get(ME, headers={"Authorization": f"Bearer {token}"})
        identities.append(resp.json())
    assert {i["username"] for i in identities} == {"alice", "Alice"}
    assert len({i["id"] for i in identities}) == 2


async def test_register_accepts_password_exactly_at_the_upper_bound(client, db_schema):
    """边界：恰好等于 `PASSWORD_MAX_LENGTH`（128 字符）必须通过——差一位都不该提前失败。"""
    resp = await client.post(REGISTER, json={"username": "alice", "password": "a1" * 64})
    assert resp.status_code == 201, resp.text


async def test_register_rejects_blank_username(client, db_schema):
    resp = await client.post(REGISTER, json={"username": "   ", "password": STRONG})
    assert resp.status_code == 422


async def test_register_rejects_username_longer_than_the_column(client, db_schema):
    """`users.username` 是 VARCHAR(64)，接口层必须先拦下，别让 DB 抛 IntegrityError。"""
    resp = await client.post(REGISTER, json={"username": "a" * 65, "password": STRONG})
    assert resp.status_code == 422


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("doc1", "长度不少于 8 位"),  # 够字符集但太短
        ("docmindab", "包含数字"),  # 只有字母
        ("12345678", "包含字母"),  # 只有数字
        ("ab", "长度不少于 8 位"),  # 两项都不满足，必须都点名
        ("密码密码密码密码", "包含字母"),  # 中文不算字母（ASCII 判定）
        ("a1" * 65, "长度不超过 128 位"),  # 130 字符：超上限
    ],
)
async def test_register_weak_password_is_rejected(
    client, db_schema, db_engine, password, expected
):
    resp = await client.post(REGISTER, json={"username": "alice", "password": password})
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "validation_error"

    # 规格要求"说明具体不满足的要求"——不能只回一句"密码不合法"
    detail_text = json.dumps(resp.json()["detail"], ensure_ascii=False)
    assert expected in detail_text, f"未说明具体不满足项：{detail_text}"

    async with db_engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM users"))).scalar_one() == 0


# ----------------------------------------------------------------------- 3.2 登录与凭证


async def test_login_returns_usable_token(client, db_schema, settings):
    await client.post(REGISTER, json={"username": "alice", "password": STRONG})

    resp = await client.post(LOGIN, json={"username": "alice", "password": STRONG})
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.TOKEN_EXPIRE_MINUTES * 60
    assert body["access_token"]

    # 凭证可立即用于访问受保护接口
    me = await client.get(ME, headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


async def test_login_failures_are_indistinguishable(client, db_schema):
    """规格「凭证不正确」：不区分"用户不存在"与"密码错误"——响应体与耗时都要一致。"""
    await client.post(REGISTER, json={"username": "alice", "password": STRONG})

    started = time.perf_counter()
    wrong_password = await client.post(LOGIN, json={"username": "alice", "password": "wrong123"})
    elapsed_wrong = time.perf_counter() - started

    started = time.perf_counter()
    unknown_user = await client.post(LOGIN, json={"username": "ghost", "password": "wrong123"})
    elapsed_unknown = time.perf_counter() - started

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()

    body = wrong_password.json()
    assert body["code"] == "unauthorized"
    assert "用户不存在" not in body["message"]
    assert "密码错误" not in body["message"]

    # 不存在用户的那条路径也必须做了真实哈希校验，不能"秒回"
    assert elapsed_wrong > 0.01 and elapsed_unknown > 0.01, (
        f"耗时 {elapsed_wrong * 1000:.1f}ms / {elapsed_unknown * 1000:.1f}ms，疑似存在捷径"
    )


async def test_login_does_the_same_hash_work_for_an_unknown_user(
    client, db_schema, monkeypatch
):
    """机制层断言：即使用户名不存在，也必须跑**恰好一次真实校验**，而不是提前 return。

    比"两条路径耗时都 >10ms"更硬 —— 耗时会受机器负载影响，这里直接看调用次数与入参
    （`None` 表示走的是 core/security.py 里的"陪跑"假摘要路径）。
    """
    from app.services import auth as auth_service

    calls: list[str | None] = []
    real_verify = auth_service.verify_password

    def spy(plain: str, hashed: str | None) -> bool:
        calls.append(hashed)
        return real_verify(plain, hashed)

    monkeypatch.setattr(auth_service, "verify_password", spy)

    resp = await client.post(LOGIN, json={"username": "ghost", "password": STRONG})
    assert resp.status_code == 401
    assert calls == [None], f"不存在的用户也必须走一次校验（实际收到 {calls}）"


async def test_login_unknown_user_is_also_rejected_after_trim(client, db_schema):
    resp = await client.post(LOGIN, json={"username": "  ghost  ", "password": STRONG})
    assert resp.status_code == 401


# ----------------------------------------------------------------------- 3.3 鉴权依赖


async def test_me_requires_credentials(client, db_schema):
    resp = await client.get(ME)
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"


async def test_me_rejects_malformed_credential(client, db_schema):
    resp = await client.get(ME, headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"


async def test_me_rejects_token_signed_with_another_key(client, db_schema, two_accounts):
    alice, _ = two_accounts
    # 伪造密钥给足 32 字节以上，避免 PyJWT 的 InsecureKeyLengthWarning 干扰汇总输出
    forged = jwt.encode(
        {"sub": str(alice.id)},
        "attacker-key-that-is-not-the-real-secret-0123456789",
        algorithm="HS256",
    )
    resp = await client.get(ME, headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


async def test_me_rejects_expired_token(client, db_schema, settings, two_accounts):
    alice, _ = two_accounts
    past = datetime.now(UTC) - timedelta(minutes=1)
    expired = jwt.encode(
        {"sub": str(alice.id), "iat": past - timedelta(hours=1), "exp": past},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    resp = await client.get(ME, headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


async def test_me_rejects_token_of_a_deleted_account(client, db_schema, db_engine, two_accounts):
    """凭证本身合法，但账号已不在库里 → 同样按未登录处理，不能把已删账号放进来。"""
    alice, _ = two_accounts
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": alice.id})

    resp = await client.get(ME, headers=alice.auth_header)
    assert resp.status_code == 401


async def test_two_accounts_see_their_own_identity(client, two_accounts):
    """双账号 fixture 的冒烟：各自凭证只映射到各自的账号。"""
    alice, bob = two_accounts
    assert alice.id != bob.id

    resp_a = await client.get(ME, headers=alice.auth_header)
    resp_b = await client.get(ME, headers=bob.auth_header)
    assert resp_a.json() == {"id": alice.id, "username": "alice"}
    assert resp_b.json() == {"id": bob.id, "username": "bob"}


async def test_identity_comes_from_the_token_not_the_request_body(two_accounts):
    """3.3 的核心判据：请求体里写别人的 user_id **不改变归属**。

    在**独立的 app 实例**上挂一条探针路由（不污染共享 app 的路由表），
    它把"依赖推导出的身份"与"请求体声明的身份"一起回显 —— 两者被区分开，才谈得上验证。

    说明：真正的越权写操作（创建知识库 / 上传文档时忽略 body 里的 user_id）
    要等 4.1 / 5.2 有对应接口后才能端到端验，本用例先锁住依赖层的行为。
    """
    alice, bob = two_accounts
    probe_app = create_app()

    @probe_app.post("/__probe/echo-identity")
    async def _echo(payload: dict, user: User = Depends(get_current_user)) -> dict:
        return {"authenticated_user_id": user.id, "received_user_id": payload.get("user_id")}

    async with AsyncClient(
        transport=ASGITransport(app=probe_app), base_url="http://testserver"
    ) as probe:
        resp = await probe.post(
            "/__probe/echo-identity",
            json={"user_id": bob.id, "username": bob.username},
            headers=alice.auth_header,
        )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"authenticated_user_id": alice.id, "received_user_id": bob.id}
