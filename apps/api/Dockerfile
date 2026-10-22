# syntax=docker/dockerfile:1
# Humbee SFA API (FastAPI). Build context: apps/api
#   docker build -t humbee-sfa-api apps/api
#   docker run --env-file <secrets.env> -e HUMBEE_SFA_PROFILE=prd -p 8001:8001 humbee-sfa-api
# Required runtime env per profile: see DEPLOY.md "API environment".
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7.4 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first (cached unless pyproject/uv.lock change).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Project itself. Editable install keeps settings.py resolving ./config relative to /app.
COPY src ./src
COPY config ./config
COPY alembic.ini ./
COPY migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.12-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HUMBEE_SFA_PROFILE=prd

RUN useradd --system --uid 10001 --no-create-home humbee

WORKDIR /app
COPY --from=builder --chown=humbee:humbee /app /app

USER humbee
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/livez', timeout=4).status == 200 else 1)"

# Secrets (JWT/HMAC/enc keys, DB creds, SMS creds, HUMBEE_API_KEY) come from the environment.
CMD ["humbee-sfa-api"]
