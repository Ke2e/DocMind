"""DocMind 后端应用入口。

分层约定（与 design.md D1 一致）：
    app/core      配置、错误契约、数据库与会话、通用客户端
    app/api       路由与依赖注入（只做参数校验与编排）
    app/schemas   Pydantic v2 请求/响应模型
    app/models    SQLAlchemy ORM 模型
    app/services  领域逻辑（状态机、管线编排等）
    app/workers   Celery 出栈任务
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import get_settings
from app.api.routes import health
from app.core.db import dispose_engine
from app.core.errors import register_exception_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 先配好日志，再读配置 —— 否则"占位项缺失"的告警会在无 handler 时被吞掉
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()  # 缺必需项时在此抛错，启动即失败
    logging.getLogger().setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.info("DocMind 后端启动：env=%s，上传目录=%s", settings.APP_ENV, settings.upload_dir)
    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="DocMind API",
        version="0.1.0",
        description="文档摄取管线：解析 → 清洗 → 分块 → 状态可查 → 失败可重试",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    return app


app = create_app()
