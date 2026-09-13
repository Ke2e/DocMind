"""Celery 任务（5.x 起接收文档处理任务，6.x 起放解析 / 分块管线，8.x 放补偿扫描）。"""

from __future__ import annotations

import logging
import time

import redis

from app.core.config import get_settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

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


@celery_app.task(name="app.workers.tasks.process_document")
def process_document(document_id: int) -> int:
    """**占位实现**：6.x 在这里接"解析 → 清洗 → 分块"的管线。

    5.x 阶段它只记一行日志、**对数据库不做任何写入**。这不是敷衍，而是刻意的：

    1. 它让"任务确实投递到了 worker"变成**可观测的证据**（e2e 用 worker 日志核对），
       而不是"库里有一行 processing_tasks 所以大概投递了吧"—— 后者只证明 API 写了库。
    2. 它让文档停留在 `uploaded`、任务行的 `stage` 保持初值，正好是 7.1 的
       「尚未被领取的任务」场景（返回"已接收"且不报错）所需的状态。
    3. 它**不抢 6.4 的活**：状态迁移必须收敛到那一个方法、并与 `stage` 同事务成对写入
       （D-025），在这里顺手改状态会立刻破坏那个约束。

    重试与异常处理也不在这里预埋：8.1 的自动重试基于本任务的失败，6.x 落地时一并接。
    """
    logger.info(
        "收到文档处理任务（5.x 占位实现，管线待 6.x 接入）：document_id=%s", document_id
    )
    return document_id
