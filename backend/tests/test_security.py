"""任务 3.1 / 3.2 的算法层核验（依据 ADR-0002）。

不连库、不起应用，只测 `app/core/security.py`——把它当纯函数测，
这样"口令怎么哈希、凭证怎么签"这件事能在最小范围内被证伪。
"""

from __future__ import annotations

import base64
import json
import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

PLAIN = "docmind123"
USER_ID = 42


def test_hash_is_argon2id_and_fits_the_password_hash_column():
    """ADR-0002 D2 的核心前提：摘要是 argon2id，且装得进 users.password_hash VARCHAR(255)。

    最后一条断言是"选 argon2id 不需要改 DDL"的机器证据，别删。
    """
    digest = hash_password(PLAIN)
    assert digest.startswith("$argon2id$")
    assert PLAIN not in digest
    assert len(digest) <= 255


def test_hash_is_salted():
    """同一口令两次哈希必须不同——否则相同口令的用户在库里会撞成同一个值。"""
    assert hash_password(PLAIN) != hash_password(PLAIN)


def test_verify_password_roundtrip():
    digest = hash_password(PLAIN)
    assert verify_password(PLAIN, digest) is True
    assert verify_password(PLAIN + "x", digest) is False


def test_verify_password_without_user_is_false_and_still_does_the_work():
    """用户名不存在（`hashed=None`）时必须返回 False，但**不能走捷径**。

    用耗时做粗判据：真跑一次 argon2 校验是几十毫秒量级，直接 return False 是微秒量级。
    这条断言守住 ADR-0002 D4 的"防时序侧信道"。
    """
    started = time.perf_counter()
    assert verify_password(PLAIN, None) is False
    elapsed = time.perf_counter() - started
    assert elapsed > 0.01, f"只用了 {elapsed * 1000:.1f}ms，说明没跑真实校验（时序侧信道）"


def test_access_token_roundtrip(settings: Settings):
    token, expires_in = create_access_token(USER_ID, settings)
    assert decode_access_token(token, settings) == USER_ID
    assert expires_in == settings.TOKEN_EXPIRE_MINUTES * 60


def test_access_token_payload_only_carries_identity_and_time(settings: Settings):
    """ADR-0002 D4：payload 只放 sub / iat / exp，不放 username、role 之类的业务字段。

    凭证里的字段越多，"某个字段被顺手当权限用"的口子就越多。
    """
    token, _ = create_access_token(USER_ID, settings)
    payload = jwt.decode(token, options={"verify_signature": False})
    assert set(payload) == {"sub", "iat", "exp"}
    assert payload["sub"] == str(USER_ID)
    assert payload["exp"] - payload["iat"] == settings.TOKEN_EXPIRE_MINUTES * 60


def test_expired_token_is_rejected(settings: Settings):
    past = datetime.now(UTC) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": str(USER_ID), "iat": past - timedelta(hours=1), "exp": past},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_token_signed_with_another_key_is_rejected(settings: Settings):
    # 伪造密钥给足 32 字节以上，避免 PyJWT 的 InsecureKeyLengthWarning 干扰汇总输出
    token = jwt.encode(
        {"sub": str(USER_ID)},
        "attacker-key-that-is-not-the-real-secret-0123456789",
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)


def test_unsigned_token_is_rejected(settings: Settings):
    """算法混淆的经典打法：把 header 的 `alg` 改成 none 并去掉签名。

    我们显式传 `algorithms=[...]` 白名单，所以它必须被拒（ADR-0002 D1）。
    """

    def b64(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    unsigned = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': str(USER_ID)})}."
    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned, settings)


@pytest.mark.parametrize("bad_sub", [None, "abc", [], {"x": 1}])
def test_token_with_unusable_subject_is_rejected(settings: Settings, bad_sub):
    payload = {"sub": bad_sub} if bad_sub is not None else {"iat": datetime.now(UTC)}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, settings)
