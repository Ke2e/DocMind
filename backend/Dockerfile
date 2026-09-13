FROM python:3.12-slim

# 刻意**不设** PIP_NO_CACHE_DIR：它会让每次构建都重新下载全部依赖。
# pip 的下载缓存在构建期、不进镜像层，所以去掉它不会让镜像变大。
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

# `--mount=type=cache` 把 pip 的下载缓存挂到持久化卷上。
# 为什么需要它：只要 `app/` 或 `pyproject.toml` 变了，这一层的构建缓存就失效、pip 会重跑；
# 有缓存挂载时它从本地缓存取 wheel，没挂则**全量重下**（本机实测一次 41 分钟，见 docs/findings.md D-033）。
# 依赖 BuildKit（Docker Desktop 默认启用）。
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip && python -m pip install .

# 迁移文件与配置一并入镜像：容器内即可执行 `alembic upgrade head`，
# 不必把库端口暴露到宿主（任务 2.2）。
# 注意 alembic.ini 必须保持纯 ASCII —— alembic 以 locale 编码读它。
COPY alembic.ini ./
COPY alembic ./alembic

# api / worker / beat 共用同一镜像，仅启动命令不同（见 docker-compose.yml）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
