"""Application configuration and infrastructure-adapter selection.

SHADOWGRAPH is ONE application with interchangeable infrastructure adapters.
`APP_MODE` selects a coherent bundle of defaults; each backend can still be
overridden individually.

    APP_MODE=local (default -- no external services required)
        DATABASE_URL  -> sqlite:///<backend>/data/shadowgraph.db
        GRAPH_BACKEND -> inprocess
        TASK_BACKEND  -> local

    APP_MODE=production
        DATABASE_URL  -> postgresql+psycopg://...   (required)
        GRAPH_BACKEND -> neo4j                      (NEO4J_* required)
        TASK_BACKEND  -> celery                     (REDIS_URL required)

Business logic never reads these values. Only the adapter factories in
``app.core.database`` (and later ``app.graph`` / ``app.tasks``) consult them,
so switching to the production stack is a configuration change, not a rewrite.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = BACKEND_DIR / "data" / "shadowgraph.db"

AppMode = Literal["local", "production"]
GraphBackend = Literal["inprocess", "neo4j"]
TaskBackend = Literal["local", "celery"]

# Relationship Confidence Score weights (Phase 5). Declared here so the scoring
# model stays configurable from the environment; not consumed until Milestone 3.
DEFAULT_CORRELATION_WEIGHTS: dict[str, int] = {
    "pgp": 30,
    "wallet": 25,
    "handle": 15,
    "infrastructure": 15,
    "stylometry": 10,
    "behavior": 5,
}


class Settings(BaseSettings):
    """Environment-driven settings. Never hard-code credentials here."""

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- identity ----------------------------------------------------------
    app_name: str = "SHADOWGRAPH"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    # ---- adapter selection -------------------------------------------------
    app_mode: AppMode = "local"
    graph_backend: GraphBackend | None = None
    task_backend: TaskBackend | None = None

    # ---- relational store --------------------------------------------------
    database_url: str | None = None
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # ---- production-only services (unused in local mode) -------------------
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None
    neo4j_database: str = "neo4j"
    redis_url: str | None = None

    # ---- auth (wired in a later milestone; no insecure default) ------------
    secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    # ---- demo data ---------------------------------------------------------
    seed_on_startup: bool = True
    demo_seed: int = 20260726

    # ---- api behaviour -----------------------------------------------------
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    default_page_size: int = 25
    max_page_size: int = 200

    correlation_weights: dict[str, int] = Field(
        default_factory=lambda: dict(DEFAULT_CORRELATION_WEIGHTS)
    )

    # ---- derived -----------------------------------------------------------
    @model_validator(mode="after")
    def _resolve_adapters(self) -> "Settings":
        production = self.app_mode == "production"

        if self.graph_backend is None:
            self.graph_backend = "neo4j" if production else "inprocess"
        if self.task_backend is None:
            self.task_backend = "celery" if production else "local"

        if self.database_url is None:
            if production:
                raise ValueError(
                    "APP_MODE=production requires DATABASE_URL "
                    "(e.g. postgresql+psycopg://user:pass@host:5432/shadowgraph)"
                )
            DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.database_url = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

        if self.graph_backend == "neo4j" and not (self.neo4j_uri and self.neo4j_user):
            raise ValueError("GRAPH_BACKEND=neo4j requires NEO4J_URI and NEO4J_USER")
        if self.task_backend == "celery" and not self.redis_url:
            raise ValueError("TASK_BACKEND=celery requires REDIS_URL")

        if not self.secret_key:
            if production:
                raise ValueError("APP_MODE=production requires SECRET_KEY")
            # Ephemeral per-process key for local development. Tokens do not
            # survive a restart, which is the correct behaviour for dev and
            # avoids shipping a guessable default in source.
            self.secret_key = secrets.token_urlsafe(48)
        return self

    @model_validator(mode="before")
    @classmethod
    def _parse_weights(cls, data: object) -> object:
        """Accept CORRELATION_WEIGHTS as a JSON object string from the env."""
        if isinstance(data, dict):
            raw = data.get("correlation_weights") or data.get("CORRELATION_WEIGHTS")
            if isinstance(raw, str):
                merged = dict(DEFAULT_CORRELATION_WEIGHTS)
                try:
                    merged.update(
                        {k: int(v) for k, v in json.loads(raw).items()
                         if k in DEFAULT_CORRELATION_WEIGHTS}
                    )
                except (ValueError, TypeError, AttributeError):
                    pass
                data = {**data, "correlation_weights": merged}
                data.pop("CORRELATION_WEIGHTS", None)
        return data

    @property
    def is_sqlite(self) -> bool:
        return (self.database_url or "").startswith("sqlite")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
