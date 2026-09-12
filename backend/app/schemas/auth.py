"""账号相关的请求 / 响应模型（任务 3.1 / 3.2）。

请求模型负责"能进来的最小集合"，响应模型负责"能出去的最小集合"——
`UserPublic` 刻意不含 `password_hash`，这是规格「响应中不包含密码或其摘要」的落点。
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings

# 字母 / 数字一律按 ASCII 判定：`str.isalpha()` 把中文也算字母，
# 那样 "密码密码" 就能通过强度校验 —— 不是规格想要的效果。
_ASCII_LETTER = re.compile(r"[A-Za-z]")
_ASCII_DIGIT = re.compile(r"[0-9]")


def _normalize_username(value: str) -> str:
    """两端空白无意义（"alice " 与 "alice" 是同一个名字），去掉后不能为空。

    除长度上限（对齐 `users.username VARCHAR(64)`）外不强加规则：
    规格没有规定用户名的字符集与最小长度，不自行发明约束。
    """
    name = value.strip()
    if not name:
        raise ValueError("用户名不能为空")
    return name


class RegisterRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(description="明文口令，仅用于本次请求，不会入库")

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        return _normalize_username(value)

    @field_validator("password")
    @classmethod
    def _check_strength(cls, value: str) -> str:
        """强度规则：长度 ≥ `PASSWORD_MIN_LENGTH` 且 ≤ `PASSWORD_MAX_LENGTH`，同时包含字母与数字，
        拒绝时说明**具体**不满足项。

        上限的用途是挡掉畸形超长输入（argon2 会把整串吃进去算），不是强度旋钮——
        与下限一样都从配置读，代码里不出现字面量。
        """
        settings = get_settings()
        unmet: list[str] = []
        if len(value) < settings.PASSWORD_MIN_LENGTH:
            unmet.append(f"长度不少于 {settings.PASSWORD_MIN_LENGTH} 位")
        if len(value) > settings.PASSWORD_MAX_LENGTH:
            unmet.append(f"长度不超过 {settings.PASSWORD_MAX_LENGTH} 位")
        if not _ASCII_LETTER.search(value):
            unmet.append("包含字母")
        if not _ASCII_DIGIT.search(value):
            unmet.append("包含数字")
        if unmet:
            raise ValueError("密码不满足要求：" + "、".join(unmet))
        return value


class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        # 与注册用同一套归一化，否则"注册时去空格、登录时不去"会变成一个谁也复现不出的登录失败
        return _normalize_username(value)


class UserPublic(BaseModel):
    """账号的对外视图 —— **绝不包含** `password_hash`。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="有效秒数，来自 TOKEN_EXPIRE_MINUTES")
