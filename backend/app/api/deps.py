"""FastAPI 依赖注入组件（任务 1.2 建立，3.x 起在此基础上加鉴权依赖）。"""

from __future__ import annotations

from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
