# 多阶段构建：uv 提供可复现安装（SPEC §13.2）
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 先复制依赖清单，利用镜像层缓存
COPY pyproject.toml uv.lock README.md ./

# 安装运行时依赖（不安装 dev 组）
RUN uv sync --frozen --no-dev

# 复制源码
COPY src ./src
COPY alembic.ini ./

# 以只读方式安装本项目包
RUN uv sync --frozen --no-dev

EXPOSE 8000 8501

# 默认启动 API；ui 服务在 compose 中覆盖 command
CMD ["uv", "run", "uvicorn", "enterprise_policy_rag.interfaces.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
