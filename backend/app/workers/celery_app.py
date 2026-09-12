"""Celery 应用。

任务 1.3 需要 worker / beat 能随 compose 一起健康启动，故此处先建立应用与最小调度；
8.3 的中断补偿周期扫描在 `beat_schedule` 中追加。
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "docmind",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 任务在 worker 崩溃时可被重新投递；配合 8.6 的幂等写入（先清后写 + 唯一约束）不会产生重复片段
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="docmind",
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    beat_schedule={
        "beat-heartbeat": {
            "task": "app.workers.tasks.beat_heartbeat",
            "schedule": settings.BEAT_HEARTBEAT_INTERVAL_SECONDS,
        },
    },
)
