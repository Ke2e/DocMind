"""密码哈希与登录凭证签发（任务 3.1 / 3.2，依据 ADR-0002）。

本模块只做纯计算：**不碰数据库、不读请求**。好处是它能脱离 Web 层被单测，
而且"身份从哪来"这件事只剩 `decode_access_token` 一个入口。

两条不可动的约束（ADR-0002）：

1. argon2 参数用库默认值，且**不从配置暴露**。这两个参数是抗爆破强度的直接旋钮，
   做成环境变量只会给人"调小一点跑得快些"的机会，而调小直接削弱整个口令库。
2. 校验凭证时必须显式给出算法白名单。拿 token header 里的 `alg` 当依据，
   正是算法混淆漏洞（CVE-2024-33663）的根因。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

logger = logging.getLogger(__name__)

# argon2id，参数取库默认（time_cost=3 / memory_cost=64MiB / parallelism=4）。
# 实测单次哈希约 56ms —— 调用方一律走线程池（见 services/auth.py），不要直接在事件循环里算。
_hasher = PasswordHasher()

# "陪跑"用的假口令：用户名不存在时拿它跑一次真实校验（见 verify_password）。
# 它必须永远不等于任何真实口令；接口层还有第二道保险——校验通过后仍要求"库里确实有该用户"。
_DUMMY_PASSWORD = "docmind-dummy-password-that-never-matches"


class InvalidTokenError(Exception):
    """凭证无法校验通过。

    **故意不区分**过期 / 签名不符 / 结构非法 —— 区分原因本身就是信息泄漏。
    """


def hash_password(plain: str) -> str:
    """把明文口令转成不可还原的 argon2id 摘要（形如 `$argon2id$...`，实测 97 字符）。"""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    """校验口令。

    `hashed` 为 None 表示"库里没有这个用户"，此时**仍然跑一次真实的哈希校验**：
    否则"响应快 = 用户不存在"本身就是可利用的时序侧信道（ADR-0002 D4）。
    """
    target = hashed if hashed is not None else _dummy_hash()
    try:
        _hasher.verify(target, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    # 走到这里说明摘要校验通过；但"陪跑"路径必须恒为 False ——
    # 万一有人拿 _DUMMY_PASSWORD 当口令注册，也不能凭它登录。
    return hashed is not None


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """惰性生成并缓存假摘要。放在模块导入时生成，会让每次进程启动白付 56ms。"""
    return _hasher.hash(_DUMMY_PASSWORD)


def create_access_token(user_id: int, settings: Settings) -> tuple[str, int]:
    """签发登录凭证，返回 `(token, 有效秒数)`。

    payload 只放 `sub` / `iat` / `exp` —— 不放 username、role 之类的业务字段：
    3.3 要求"身份只由凭证推导"，凭证里字段越多，"某个字段被顺手当权限用"的口子就越多。
    """
    now = datetime.now(UTC)
    expires_in = settings.TOKEN_EXPIRE_MINUTES * 60
    token = jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(seconds=expires_in)},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, expires_in


def decode_access_token(token: str, settings: Settings) -> int:
    """解析并校验凭证，返回 `user_id`；任何失败都抛 `InvalidTokenError`。"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            # 白名单只认配置里那一种算法：绝不允许 None，也绝不信任 token 自称的 alg
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError as exc:
        # 具体原因（过期 / 签名不符 / 格式非法）只进日志，不进响应
        logger.info("凭证校验失败：%s: %s", type(exc).__name__, exc)
        raise InvalidTokenError("凭证无效或已过期") from exc

    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("凭证缺少合法的 sub") from exc
