"""账号领域逻辑（任务 3.1 / 3.2）。

哈希是 CPU 密集的（实测单次约 56ms）—— 一律 `asyncio.to_thread` 丢线程池，
不要在事件循环里直接算：一次登录把整个进程卡住 56ms，同进程的其他请求全得等。
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.security import hash_password, verify_password
from app.models import User

_USERNAME_TAKEN_MESSAGE = "该用户名已被占用，请换一个"


async def register_user(session: AsyncSession, *, username: str, password: str) -> User:
    """创建账号。用户名已被占用时抛 `ConflictError`（409）。"""
    # 先查一次只是为了给可读提示；真正的唯一性由 uq_users_username 兜底 ——
    # "先查后写"在并发下必有竞态，所以下面还要接住 IntegrityError。
    existing = await session.scalar(select(User.id).where(User.username == username))
    if existing is not None:
        raise ConflictError(_USERNAME_TAKEN_MESSAGE)

    user = User(
        username=username,
        password_hash=await asyncio.to_thread(hash_password, password),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        # 两个请求同时通过了上面的检查，唯一约束会拦下后到的那个。
        # 会话已进入失败状态，回滚由 session_scope 负责（异常继续上抛）。
        raise ConflictError(_USERNAME_TAKEN_MESSAGE) from exc
    return user


async def authenticate(session: AsyncSession, *, username: str, password: str) -> User | None:
    """校验凭证。失败一律返回 None —— **不告诉调用方是哪一步错了**。"""
    user = await session.scalar(select(User).where(User.username == username))
    # 无论用户是否存在都走一次真实校验：耗时差异本身就是"该用户是否存在"的泄漏。
    ok = await asyncio.to_thread(
        verify_password, password, user.password_hash if user is not None else None
    )
    return user if ok else None
