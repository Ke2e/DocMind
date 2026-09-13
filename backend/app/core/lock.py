"""分布式锁（任务 5.3）。

用途只有一个：**同一文档的处理任务只被投递一次**（design.md「Risks」里的
"[重试叠加导致同一文档被并发处理] → 投递前加分布式锁（复用 Redis），并靠唯一约束兜底"）。

实现要点（这几条都是刻意选的，别随手改）：

1. **加锁用 `SET key token NX PX ttl`**，不用 `SETNX` + `EXPIRE` 两步 ——
   两条命令之间进程挂掉就会留下一个**永不过期的锁**，把该文档永久卡死。
   单条 `SET` 带 `NX`/`PX` 在 Redis 里是原子的。
2. **释放用 Lua 比对令牌再删**，不直接 `DEL` ——
   如果本次临界区超时（TTL 到期，锁已自动释放并被别人抢走），直接 `DEL` 会**删掉别人的锁**。
   `GET` + 比较 + `DEL` 必须原子，故写在服务端脚本里。
   （刻意不引入 `redis-py` 的 `Lock` 高阶封装：本项目只用这一个语义，
   自己写 12 行 Lua 比多一层不确定行为的封装更好读。）
3. **拿不到锁不重试等待，直接返回 `acquired=False`** —— 调用方（投递）据此判断
   "此刻已有另一个投递在进行"并跳过。这不是"丢任务"：任务行已经在库里，
   真被卡住的任务由 8.3 的中断补偿扫描重新调度（design.md D7 就是为这个场景设计的）。

锁的粒度是 `document_id`，TTL 是**安全网**而不是业务参数：
临界区只有"一条 INSERT + 一次投递"（毫秒级），TTL 只需远大于它。
故写成模块常量而不是配置项 —— 与 ADR-0002 把 argon2 参数排除在 Settings 之外同理：
给一个旋钮就会有人把它调到 0，那不是可调项，是踩着才会发现的地雷。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final
from uuid import uuid4

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

#: 锁的存活时间（毫秒）。临界区毫秒级，10 秒足够长；同时短到"持锁进程崩了"也能自愈。
DEFAULT_LOCK_TTL_MILLISECONDS: Final = 10_000

#: 只有令牌对得上才删。KEYS[1]=锁键，ARGV[1]=本次持有的令牌。
_RELEASE_SCRIPT: Final = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


@asynccontextmanager
async def distributed_lock(
    client: aioredis.Redis,
    key: str,
    *,
    ttl_milliseconds: int = DEFAULT_LOCK_TTL_MILLISECONDS,
) -> AsyncIterator[bool]:
    """尝试获取 `key` 上的锁，`yield` 是否获取成功；退出时若仍持有则释放。

    **调用方必须检查 `yield` 出来的布尔值**——拿到 `False` 表示锁在别人手里，
    该走"跳过"分支而不是照常做事，否则这把锁就白加了。
    """
    token = uuid4().hex
    acquired = bool(await client.set(key, token, nx=True, px=ttl_milliseconds))
    if not acquired:
        logger.info("分布式锁被占用，跳过：key=%s", key)
    try:
        yield acquired
    finally:
        if acquired:
            await client.eval(_RELEASE_SCRIPT, 1, key, token)
