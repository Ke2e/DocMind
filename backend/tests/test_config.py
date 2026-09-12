"""任务 1.4 验证：三档配置行为 + 代码中不得硬编码模型名与地址。

三档：
- 必需项缺失 -> 启动失败并指出缺哪一项
- 只缺占位项 -> 正常启动并打印告警
- 业务参数 -> 有默认值，且可被配置覆盖（FR-006 / SC-007 的前提）
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.core.config import (
    PLACEHOLDER_FIELDS,
    ConfigError,
    load_settings,
)

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:5433/db",
    "REDIS_URL": "redis://127.0.0.1:6380/0",
    "SECRET_KEY": "test-secret-key",
}

# 模型名与服务商地址一律不得出现在代码里（必须从配置读）
FORBIDDEN_LITERALS = (
    "deepseek",
    "qwen",
    "dashscope",
    "compatible-mode",
    "text-rerank",
    "api/v1/services",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """清掉进程环境里的配置项，让结果只取决于传入的 env_file。"""
    for name in (*REQUIRED_ENV, *PLACEHOLDER_FIELDS):
        monkeypatch.delenv(name, raising=False)


def _write_env(tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    lines = [f"{k}={v}" for k, v in {**REQUIRED_ENV, **(extra or {})}.items()]
    env_file = tmp_path / "env"
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_file


def test_missing_required_fails_and_names_them(clean_env: None) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_settings(env_file=None)

    message = str(excinfo.value)
    for name in REQUIRED_ENV:
        assert name in message, f"报错信息未指出缺失项：{name}"


def test_only_placeholders_missing_warns_but_starts(
    clean_env: None, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    env_file = _write_env(tmp_path)

    with caplog.at_level(logging.WARNING):
        settings = load_settings(env_file=env_file)

    assert "模型网关配置未就位" in caplog.text, "只缺占位项时必须打印告警"
    assert all(getattr(settings, name) is None for name in PLACEHOLDER_FIELDS)


def test_business_params_have_defaults(clean_env: None, tmp_path: Path) -> None:
    settings = load_settings(env_file=_write_env(tmp_path))

    assert settings.CHUNK_SIZE_TOKENS == 512
    assert settings.CHUNK_OVERLAP_TOKENS == 64
    assert settings.MAX_UPLOAD_MB == 50
    assert settings.max_upload_bytes == 50 * 1024 * 1024
    assert settings.allowed_extensions == frozenset({"pdf", "docx", "md", "txt"})
    assert settings.AUTO_RETRY_MAX == 2
    assert settings.MANUAL_RETRY_MAX == 3
    assert settings.PASSWORD_MIN_LENGTH == 8


def test_business_params_are_overridable(clean_env: None, tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        {
            "CHUNK_SIZE_TOKENS": "256",
            "CHUNK_OVERLAP_TOKENS": "32",
            "MAX_UPLOAD_MB": "10",
            "ALLOWED_EXTENSIONS": "PDF, .txt",
        },
    )
    settings = load_settings(env_file=env_file)

    assert settings.CHUNK_SIZE_TOKENS == 256
    assert settings.CHUNK_OVERLAP_TOKENS == 32
    assert settings.max_upload_bytes == 10 * 1024 * 1024
    # 白名单归一化：大小写无关、可带前导点
    assert settings.allowed_extensions == frozenset({"pdf", "txt"})


def test_no_hardcoded_model_or_endpoint_in_app_source() -> None:
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders: list[str] = []

    for path in app_dir.rglob("*.py"):
        lowered = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_LITERALS:
            if token in lowered:
                offenders.append(f"{path.relative_to(app_dir)} 命中 {token!r}")

    assert not offenders, "代码中出现硬编码的模型名或地址：" + "；".join(offenders)
