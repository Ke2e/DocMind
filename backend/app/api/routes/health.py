"""健康检查（任务 1.2）。

刻意分成两个端点：
- `/health/live`：进程存活，**不触碰任何外部依赖** —— 容器 liveness 探针用它，避免 PG 抖动把 API 打挂
- `/health/ready`：就绪，逐个探测 PostgreSQL 与 Redis —— 容器 readiness 探针用它
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_settings
from app.core.config import Settings
from app.core.db import check_database, check_redis
from app.core.errors import ErrorCode, error_payload

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="进程存活检查（不依赖外部服务）")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="就绪检查（探测 PostgreSQL 与 Redis）")
async def ready(response: Response, settings: Settings = Depends(get_settings)) -> dict:
    checks = {
        "database": await check_database(settings),
        "redis": await check_redis(settings),
    }
    failed = {name: reason for name, reason in checks.items() if reason}
    if failed:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return error_payload(
            ErrorCode.UPSTREAM_ERROR,
            "依赖服务未就绪",
            {"checks": checks},
        )
    return {"status": "ok", "checks": checks}
