# Multi-stage build using uv. Produces a slim, non-root runtime image.
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
# Resolve dependencies from the lockfile (no dev extras) into /app/.venv.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM base
RUN useradd -u 10001 -r -s /usr/sbin/nologin zest
COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH"
USER zest
EXPOSE 8091
# Compose runs "alembic upgrade head && uvicorn ..."; the default CMD just serves.
CMD ["uvicorn", "zest_data_api.main:app", "--host", "0.0.0.0", "--port", "8091"]
