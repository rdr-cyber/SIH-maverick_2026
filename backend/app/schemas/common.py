"""Shared response contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Envelope for every list endpoint."""

    items: list[T]
    total: int = Field(description="Total rows matching the filter, ignoring paging")
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class AdapterInfo(BaseModel):
    """Which infrastructure adapters this process is running with."""

    app_mode: Literal["local", "production"]
    database: str = Field(description="SQLAlchemy dialect in use, e.g. sqlite / postgresql")
    graph_backend: Literal["inprocess", "neo4j"]
    task_backend: Literal["local", "celery"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    time: datetime
    adapters: AdapterInfo
    checks: dict[str, str] = Field(description="Per-dependency probe results")


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"
