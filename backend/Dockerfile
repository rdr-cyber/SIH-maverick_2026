# ============================================================================
# SHADOWGRAPH — Backend Dockerfile
# Multi-stage build: base → dev → prod
# ============================================================================

# --- Base stage ---------------------------------------------------------------
FROM python:3.12-slim AS base

WORKDIR /app

# System deps for psycopg2-binary and fpdf2
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

# Non-root user
RUN addgroup --system shadowgraph && \
    adduser --system --ingroup shadowgraph shadowgraph && \
    mkdir -p /app/data && chown -R shadowgraph:shadowgraph /app

USER shadowgraph

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
