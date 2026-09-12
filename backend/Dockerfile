FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN python -m pip install --upgrade pip && python -m pip install .

# 迁移文件与配置一并入镜像：容器内即可执行 `alembic upgrade head`，
# 不必把库端口暴露到宿主（任务 2.2）。
# 注意 alembic.ini 必须保持纯 ASCII —— alembic 以 locale 编码读它。
COPY alembic.ini ./
COPY alembic ./alembic

# api / worker / beat 共用同一镜像，仅启动命令不同（见 docker-compose.yml）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
