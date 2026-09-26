# Multi-stage build for the product image: both entry points, `leadradar-api` and
# `leadradar-worker` ([Python Toolchain](/guidelines/python.md#toolchain)).

FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv==0.11.28

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 leadradar
WORKDIR /app

COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:${PATH}"

USER leadradar

# The command is set per-container by compose.yaml: `leadradar-api` or `leadradar-worker`.
