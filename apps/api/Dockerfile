# syntax=docker/dockerfile:1
# Humbee SFA API (FastAPI). Build context: REPO ROOT
#   docker build -f apps/api/Dockerfile -t humbee-sfa-api .
#   docker run --env-file <secrets.env> -e HUMBEE_SFA_PROFILE=prd -p 8001:8001 humbee-sfa-api
# Required runtime env per profile: see DEPLOY.md "API environment".
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7.4 /uv /usr/local/bin/uv

# Slow-network tolerance (uv's 30s default times out on Docker Desktop).
ARG UV_HTTP_TIMEOUT=300
ARG UV_CONCURRENT_DOWNLOADS=4

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_HTTP_TIMEOUT=$UV_HTTP_TIMEOUT \
    UV_CONCURRENT_DOWNLOADS=$UV_CONCURRENT_DOWNLOADS

WORKDIR /app

# Dependencies first (cached unless pyproject/uv.lock change).
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Project itself. Editable install keeps settings.py resolving ./config relative to /app.
COPY apps/api/src ./src
COPY apps/api/config ./config
# Alembic (script_location = %(here)s/migrations): DEPLOY.md runs `alembic upgrade head` in this image.
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/migrations ./migrations
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
