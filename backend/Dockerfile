# ============================================================================
# TRILOK TRACE — Backend Dockerfile
# Multi-stage build: base → dev → prod
# The `prod` target is what docker-compose.yml `backend` builds (target: prod).
# Boots via migrate-on-boot: APP_MODE=production runs `alembic upgrade head`
# at startup (see app/main.py lifespan), so the schema is always current.
# ============================================================================

# --- Base stage ---------------------------------------------------------------
FROM python:3.12-slim AS base

WORKDIR /app

# System deps for psycopg (binary wheel needs no libpq at runtime, but keep
# gcc/libpq for source fallback builds) and libpq data files.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# --- Dev stage (hot-reload) ---------------------------------------------------
FROM base AS dev

RUN pip install --no-cache-dir watchfiles

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- Prod stage ---------------------------------------------------------------
FROM base AS prod

# Non-root user (SECURITY.md §8); reports-output is the writable volume.
RUN addgroup --system trilok_trace && \
    adduser --system --ingroup trilok_trace trilok_trace && \
    mkdir -p /app/data /app/reports-output && \
    chown -R trilok_trace:trilok_trace /app

USER trilok_trace

EXPOSE 8000

# migrate-on-boot, then serve (compose mounts app/ read-only for dev sync)
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
