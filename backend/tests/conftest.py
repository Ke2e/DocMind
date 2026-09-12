"""测试脚手架（任务 1.5，2.x 修订连接串来源）。

设计要点：
1. **配置隔离** —— 在导入应用之前用环境变量顶掉 `.env`（环境变量优先级高于 dotenv），
   测试绝不连到开发库 / 生产库。
2. **不依赖已启动的 worker** —— 接口测试只走 ASGI，任务投递在后续用例中替换为记录桩。
3. **测试库 schema 建 / 销毁** —— 用例前后各清一次，保证测试库无残留表。
   库不可达时跳过（而不是伪装通过）。

测试库前置（本机无本地 PG，只能用 compose 起的实例）：

    docker exec docmind-pg psql -U docmind -d docmind -c "CREATE DATABASE docmind_test OWNER docmind"
    cd backend && .venv/Scripts/python.exe -m pytest -q

连接串来源：从仓库根 `.env` 读 POSTGRES_* / PG_HOST_PORT 拼出 `docmind_test`，
避免把口令在测试里再抄一份（2026-09-12 实测：原先硬编码的口令与 `.env` 不一致，
会让所有库相关用例静默 skip）。要接别的库时用 `TEST_DATABASE_URL` 覆盖。
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _local_env() -> dict[str, str]:
    """读仓库根 `.env`。只解析 KEY=VALUE 与 `#` 注释，不引入新依赖。"""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return {}
    values: dict[str, str] = {}
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _test_database_url() -> str:
    env = _local_env()
    user = env.get("POSTGRES_USER", "docmind")
    password = env.get("POSTGRES_PASSWORD", "docmind")
    port = env.get("PG_HOST_PORT", "5433")
    return f"postgresql+asyncpg://{user}:{password}@127.0.0.1:{port}/docmind_test"


# 必须在 import app.* 之前完成，否则 Settings 会读到开发者本地 .env。
# 这里用直接赋值而非 setdefault：测试必须指向测试库，不允许被外泄的 DATABASE_URL 带偏。
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or _test_database_url()
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6380/15")
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
    # 从包导入（而不是 app.models.base）：保证 5 张表都注册进 metadata，
    # 否则 create_all 只会建被显式 import 的那张表
    from app.models import Base

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
