"""配置系统（任务 1.4）。

单一事实来源：仓库根目录的 `.env`（compose 与后端共用），样例见 `.env.example`。

分三档：
- 本期必需：缺失即启动失败（DATABASE_URL / REDIS_URL / SECRET_KEY）
- 本期占位：W5 不参与数据流，缺失只告警（模型网关相关）
- 业务参数：一律带默认值，但**全部可从配置覆盖**，代码中不得出现字面量
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# backend/app/core/config.py -> parents[3] 即仓库根
REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"

# 本期必需项，顺序即报错时的展示顺序
REQUIRED_FIELDS: tuple[str, ...] = ("DATABASE_URL", "REDIS_URL", "SECRET_KEY")

# 本期占位项：缺失仅告警（W5 不调用任何模型服务）
PLACEHOLDER_FIELDS: tuple[str, ...] = (
    "BASE_URL",
    "API_KEY",
    "GENERATIVE_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    "RERANK_MODEL",
    "RERANK_BASE_URL",
)


class ConfigError(RuntimeError):
    """配置缺失导致无法启动。消息中明确指出缺哪一项。"""


# 哨兵：区分"未传 env_file（用默认 .env）"与"显式不读 .env（传 None）"
_UNSET_DEFAULT = object()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ---------------- 本期必需 ----------------
    DATABASE_URL: str = Field(description="PostgreSQL 异步连接串（postgresql+asyncpg://）")
    REDIS_URL: str = Field(description="Redis 连接串，兼作 Celery broker 与结果后端")
    SECRET_KEY: str = Field(description="登录凭证签名密钥")

    # ---------------- 模型网关（本期占位）----------------
    # 一个 BASE_URL + 一个 API_KEY 覆盖生成 / 嵌入 / 重排三个用途
    BASE_URL: str | None = None
    API_KEY: str | None = None
    GENERATIVE_MODEL: str | None = None
    EMBEDDING_MODEL: str | None = None
    EMBEDDING_DIM: int | None = None
    RERANK_MODEL: str | None = None
    # 重排走服务商原生 rerank 路径，不在 OpenAI 兼容入口下（实测 404），
    # 地址必须整条取自本项，不得在代码里拼
    RERANK_BASE_URL: str | None = None

    # ---------------- 运行环境 ----------------
    APP_ENV: str = "dev"
    LOG_LEVEL: str = "INFO"
    API_PORT: int = 8000

    # ---------------- 文件存储（任务 5.1）----------------
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_MB: int = 50
    ALLOWED_EXTENSIONS: str = "pdf,docx,md,txt"

    # ---------------- 分块参数（任务 6.2，FR-006 / SC-007）----------------
    CHUNK_SIZE_TOKENS: int = 512
    CHUNK_OVERLAP_TOKENS: int = 64

    # ---------------- 重试与中断补偿（任务 8.1 / 8.2 / 8.3）----------------
    AUTO_RETRY_MAX: int = 2
    MANUAL_RETRY_MAX: int = 3
    RETRY_BACKOFF_BASE_SECONDS: int = 5
    STUCK_TASK_THRESHOLD_SECONDS: int = 600
    # beat 心跳周期（容器健康探针依赖它，见 docker-compose.yml 的 beat healthcheck）
    BEAT_HEARTBEAT_INTERVAL_SECONDS: int = 30

    # ---------------- 鉴权（任务 3.1 / 3.2）----------------
    PASSWORD_MIN_LENGTH: int = 8
    # 上限不是强度旋钮，而是"别让超长输入白耗 argon2 算力"的输入护栏；
    # 与下限一样属业务参数，故进配置（1.4 的"代码里不得出现字面量"）
    PASSWORD_MAX_LENGTH: int = 128
    TOKEN_EXPIRE_MINUTES: int = 60 * 24
    JWT_ALGORITHM: str = "HS256"

    # ---------------- 派生属性（把字符串配置解析成可用结构）----------------

    @property
    def upload_dir(self) -> Path:
        """相对路径按仓库根解析，绝对路径原样返回。"""
        return self.UPLOAD_DIR if self.UPLOAD_DIR.is_absolute() else (REPO_ROOT / self.UPLOAD_DIR)

    @property
    def allowed_extensions(self) -> frozenset[str]:
        """扩展名白名单，统一小写、去掉前导点，不区分大小写比较。"""
        return frozenset(
            ext.strip().lstrip(".").lower()
            for ext in self.ALLOWED_EXTENSIONS.split(",")
            if ext.strip()
        )

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


def _missing_required_names(exc: ValidationError) -> list[str]:
    missing = {
        str(err["loc"][-1])
        for err in exc.errors()
        if err.get("type") == "missing" and err.get("loc")
    }
    # 按 REQUIRED_FIELDS 声明顺序输出，报告更稳定
    ordered = [name for name in REQUIRED_FIELDS if name in missing]
    ordered.extend(sorted(missing - set(ordered)))
    return ordered


def load_settings(env_file: Path | str | None = _UNSET_DEFAULT) -> Settings:
    """加载配置。缺必需项时抛 ConfigError，并指出具体缺哪一项。

    `env_file` 显式传 None 表示**不读 .env**（只用环境变量），
    用于验证"缺必需项即失败"的行为，见 tests/test_config.py。
    """
    extra: dict[str, object] = {}
    if env_file is not _UNSET_DEFAULT:
        extra["_env_file"] = env_file
    try:
        settings = Settings(**extra)
    except ValidationError as exc:
        missing = _missing_required_names(exc)
        if missing:
            raise ConfigError(
                "配置缺失，应用无法启动：" + "、".join(missing) + f"（读取自 {ENV_FILE} 或环境变量；"
                "请参考 .env.example 补齐）"
            ) from exc
        raise ConfigError(f"配置非法，应用无法启动：{exc}") from exc

    _warn_placeholders(settings)
    return settings


def _warn_placeholders(settings: Settings) -> None:
    """占位项缺失只告警，不阻断启动（W5 不调用任何模型服务）。"""
    absent = [name for name in PLACEHOLDER_FIELDS if getattr(settings, name, None) in (None, "")]
    if absent:
        logger.warning(
            "模型网关配置未就位：%s —— 本期（W5）不调用模型服务，缺失不影响启动；"
            "接入向量化（002）前必须补齐。",
            "、".join(absent),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例配置。API 与 Celery worker 共用同一入口。"""
    return load_settings()
