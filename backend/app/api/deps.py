"""FastAPI 依赖注入组件（任务 1.2 建立，3.3 起承载鉴权依赖，5.3 起提供 Redis 客户端）。

鉴权的**唯一**入口是 `get_current_user`：身份只从 `Authorization: Bearer` 里的凭证推导，
不接受请求体或查询参数里声明的用户标识（规格「数据归属由登录态决定」）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import session_scope
from app.core.errors import UnauthorizedError
from app.core.redis import get_redis
from app.core.security import InvalidTokenError, decode_access_token
from app.models import User

__all__ = [
    "Settings",
    "get_settings",
    "get_db_session",
    "get_current_user",
    "get_redis_client",
]


# auto_error=False：缺凭证时由我们自己抛错，好让 401 的响应体走统一错误契约。
# （内置行为会抛英文的 "Not authenticated"，与其余错误响应体的形状与文案都不一致。）
# tokenUrl 仅供 OpenAPI 文档的授权按钮使用；本项目登录走 JSON 而非表单，文档里那一步用不上。
_bearer_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_db_session(settings: SettingsDep) -> AsyncIterator[AsyncSession]:
    """每请求一个事务边界：正常结束提交，抛异常回滚（见 core/db.py 的 session_scope）。"""
    async with session_scope(settings) as session:
        yield session


async def get_current_user(
    # 注意：OAuth2PasswordBearer 返回的是**原始 token 字符串**（不是 HTTPAuthorizationCredentials，
    # 那个是 HTTPBearer 的返回类型）——刚从 `credentials.credentials` 取值的写法会把 401 变成 500。
    token: Annotated[str | None, Depends(_bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: SettingsDep,
) -> User:
    """从凭证推导当前账号。

    三种失败（没带凭证 / 凭证不可用 / 账号已不存在）都返回同一个 401，
    响应体里不出现任何能区分它们的信息。
    """
    if token is None:
        raise UnauthorizedError("请先登录")
    try:
        user_id = decode_access_token(token, settings)
    except InvalidTokenError:
        raise UnauthorizedError("登录状态已失效，请重新登录") from None

    user = await session.get(User, user_id)
    if user is None:
        raise UnauthorizedError("登录状态已失效，请重新登录")
    return user


def get_redis_client(settings: SettingsDep) -> aioredis.Redis:
    """进程内常驻的 Redis 客户端（任务 5.3 的投递锁用它）。

    刻意**不用** `yield` 包成"每请求建/销"：客户端自带连接池，它的生命周期是进程级的，
    每请求开关反而会把连接池的意义抹掉。释放由 FastAPI lifespan 的收尾统一负责
    （见 `app/main.py`）。
    """
    return get_redis(settings)
