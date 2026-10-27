# syntax=docker/dockerfile:1

# ---------- Stage 1: builder — install dependencies into a virtualenv ----------
FROM python:3.12-slim AS builder

# uv as a single static binary, copied from its official image (pinned version)
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

# compile .pyc at build time (faster start); copy files instead of hard-linking from the cache
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, code second: this layer is only rebuilt when pyproject.toml/uv.lock change,
# not on every code edit (layer caching).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

# ---------- Stage 2: runtime — only what's needed to run ----------
FROM python:3.12-slim

# unprivileged user with a fixed UID (Kubernetes can then enforce runAsNonRoot)
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER 10001
EXPOSE 8000

# Docker's own health check (Kubernetes ignores this and uses its probes instead)
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
