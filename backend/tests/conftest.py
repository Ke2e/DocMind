"""测试脚手架（任务 1.5）。

设计要点：
1. **配置隔离** —— 在导入应用之前用环境变量顶掉 `.env`（环境变量优先级高于 dotenv），
   测试绝不连到开发库 / 生产库。
2. **不依赖已启动的 worker** —— 接口测试只走 ASGI，任务投递在后续用例中替换为记录桩。
3. **测试库 schema 建 / 销毁** —— 用例前后各清一次，保证测试库无残留表。
   库不可达时跳过（而不是伪装通过），需要先用 compose 起 pg。
"""

from __future__ import annotations

import os

# 必须在 import app.* 之前完成，否则 Settings 会读到开发者本地 .env
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://docmind:docmind@127.0.0.1:5433/docmind_test",
)
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6380/15")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.api.deps import get_settings  # noqa: E402
from app.core.config import Settings  # noqa: E402


@pytest.fixture(scope="session")
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture(scope="session")
def app(settings: Settings) -> FastAPI:
    from app.main import create_app

    return create_app()


def _transport(app: FastAPI, *, raise_app_exceptions: bool) -> ASGITransport:
    return ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """常规客户端：应用内异常向上抛，便于测试暴露问题。"""
    async with AsyncClient(
        transport=_transport(app, raise_app_exceptions=True),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture
async def raw_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """容忍应用内异常的客户端：用于验证 500 错误响应体契约。"""
    async with AsyncClient(
        transport=_transport(app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture(scope="session")
async def db_engine(settings: Settings):
    """连不上测试库就跳过，不伪装通过。"""
    from app.core.db import check_database, get_engine

    reason = await check_database(settings)
    if reason:
        pytest.skip(f"测试库不可达（{reason}），请先 docker compose up -d pg")
    yield get_engine(settings)


@pytest.fixture
async def db_schema(db_engine) -> AsyncIterator[None]:
    """用例前后各清一次测试库 schema，确保无残留表。"""
    from app.models.base import Base

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
