"""账号接口（任务 3.1 / 3.2 / 3.3）。

路由只做参数校验与编排，领域逻辑在 `app/services/auth.py`。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, get_settings
from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.security import create_access_token
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="注册账号",
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """注册。响应只回 `id` 与 `username`，不含口令或其摘要。"""
    return await auth_service.register_user(
        session, username=payload.username, password=payload.password
    )


@router.post("/login", response_model=TokenResponse, summary="登录并获取登录凭证")
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    user = await auth_service.authenticate(
        session, username=payload.username, password=payload.password
    )
    if user is None:
        # 规格要求"不区分用户不存在与密码错误" → 同一个错误码、同一句文案。
        # 耗时也被拉平（services/auth.py 里对不存在的用户同样跑一次校验）。
        raise UnauthorizedError("用户名或密码不正确")
    token, expires_in = create_access_token(user.id, settings)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserPublic, summary="查看当前登录账号")
async def me(current_user: User = Depends(get_current_user)) -> User:
    """受保护接口：身份完全来自凭证。

    在 4.x / 5.x 的内容接口出现之前，它既是账号体系的自省接口，
    也是 3.3 验收"无凭证 / 伪造凭证被拒"的落点。
    """
    return current_user
