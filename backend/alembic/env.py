"""Alembic 运行环境（任务 2.2）。

与默认模板的三点差异：

1. **连库地址取自应用配置**（`app.core.config.get_settings().DATABASE_URL`），
   不在 `alembic.ini` 里存第二份连接串——密钥只有一个来源，容器内外也不用各改一次。
   `DATABASE_URL` 环境变量优先级高于 `.env`，因此要迁移测试库只需：
   `DATABASE_URL=postgresql+asyncpg://…/docmind_test alembic upgrade head`
2. **导入整个模型包**（`import app.models`）而不是单个模块，保证 5 张表都进 metadata；
   漏一张表 autogenerate 会凭空生成 DROP TABLE。
3. `compare_type=True`：只改列类型（如 VARCHAR 长度）也能被测出来。

**注意 `alembic.ini` 必须保持纯 ASCII**：alembic 用 locale 编码读该文件，
本机（中文 Windows）是 GBK，写 UTF-8 中文注释会让 CLI 直接
`UnicodeDecodeError`（2026-09-12 实测踩到）。配置项的中文说明放在本文件里（.py 恒按 UTF-8 读）。
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401 - 副作用：把 5 张表注册进 Base.metadata
from alembic import context
from app.core.config import get_settings
from app.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """应用配置里的连接串。`%` 需转义——configparser 会做插值。"""
    return get_settings().DATABASE_URL.replace("%", "%%")


def run_migrations_offline() -> None:
    """离线模式：只渲染 SQL，不连库（`alembic upgrade head --sql`）。"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式：asyncpg 引擎跑同步迁移体（SQLAlchemy 官方异步模板做法）。"""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
