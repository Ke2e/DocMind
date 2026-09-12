"""数据库与会话（SQLAlchemy 2.0 async）。

只提供引擎 / 会话工厂与连通性探测；模型与迁移分别在 `app/models` 与 `alembic/`。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings) -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(settings),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope(settings: Settings) -> AsyncIterator[AsyncSession]:
    """事务边界：正常退出提交，异常回滚。"""
    factory = get_session_factory(settings)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def check_database(settings: Settings) -> str | None:
    """返回 None 表示连通；否则返回可读原因（不含连接串与密钥）。"""
    try:
        engine = get_engine(settings)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return None
    except Exception as exc:  # noqa: BLE001 - 探测接口需要吞掉任何连接异常
        return f"数据库不可用：{type(exc).__name__}"


async def check_redis(settings: Settings) -> str | None:
    """返回 None 表示连通；否则返回可读原因。"""
    client: aioredis.Redis | None = None
    try:
        client = aioredis.from_url(settings.REDIS_URL)
        await client.ping()
        return None
    except Exception as exc:  # noqa: BLE001
        return f"缓存不可用：{type(exc).__name__}"
    finally:
        if client is not None:
            await client.aclose()
