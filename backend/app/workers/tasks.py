"""Celery 任务（6.x 起放解析 / 分块管线，8.x 放补偿扫描）。"""

from __future__ import annotations

import time

import redis

from app.core.config import get_settings
from app.workers.celery_app import celery_app

# beat 心跳键：由 beat 触发、worker 写回，容器健康探针据此判断整条链路是否连通
HEARTBEAT_KEY = "docmind:beat:heartbeat"


@celery_app.task(name="app.workers.tasks.beat_heartbeat")
def beat_heartbeat() -> int:
    settings = get_settings()
    now = int(time.time())
    client = redis.Redis.from_url(settings.REDIS_URL)
    try:
        # TTL 取 3 个心跳周期：超过即为过期，说明 beat 或 worker 已停摆
        client.set(
            HEARTBEAT_KEY,
            now,
            ex=max(settings.BEAT_HEARTBEAT_INTERVAL_SECONDS * 3, 30),
        )
    finally:
        client.close()
    return now
