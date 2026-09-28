"""Global pytest isolation for TRILOK TRACE.

Two problems this solves (both bit us in real runs):

1. DATA POLLUTION: several suites never set DATABASE_URL, so ``create_app()``
   inside a test resolved the *default demo database*
   (backend/data/trilok_trace.db). Ingestion smoke tests then persisted
   INGESTED:* relationships and orphan evidence rows into the demo data.

2. HANGS: the same suites seed that shared SQLite file on import while a
   live uvicorn holds WAL locks on it — pytest then stalls indefinitely.

Fix: force a private in-memory database for the whole test process BEFORE
any app module is imported. Suites that set their own DATABASE_URL
(test_phase2/test_full use sqlite:/// scratch DBs; alembic tests pass -x
db_url) still override it afterwards — env vars set later in the module
win at create_app() time, so this only supplies the previously-missing
default. File-based suites like test_phase2 remain unaffected.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SEED_ON_STARTUP", "true")
# The local dev backend/.env raises RATE_LIMIT_PER_MINUTE to 600; the limiter
# test needs the documented default contract, so pin it for the test process.
os.environ["RATE_LIMIT_PER_MINUTE"] = "120"
# Pin a fixed secret so JWT assertions are deterministic across the run.
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
