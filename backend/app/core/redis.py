"""常驻 Redis 客户端的生命周期（任务 5.3 起使用）。

与 `core/db.py` 同一套路：进程内单例 + 由 FastAPI lifespan 在收尾时释放。

**为什么不并进 `core/db.py`**：那里的 `check_redis` 只是健康探测，它按需建连接、
探完立刻关（探测不该污染连接池）；这里提供的是**常驻客户端**，服务的是"每个写请求都要用一次"
的投递锁。两者生命周期相反，混在一个模块里会让"谁负责关"变得含糊。
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import Settings

_redis: aioredis.Redis | None = None


def get_redis(settings: Settings) -> aioredis.Redis:
    """进程内单例客户端。

    `decode_responses=True`：投递锁要用 `GET`/`EVAL` 比对令牌（字符串），
    不设它拿到的是 bytes，比较时得处处 `.decode()`，容易漏。
    """
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def dispose_redis() -> None:
    """释放连接池。测试里也会调它，以便换 `REDIS_URL` 后重新建客户端。"""
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None
