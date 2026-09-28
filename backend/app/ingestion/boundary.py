"""Ingestion connector boundary — DATABASE.md §2 guardrail.

**Rule (locked):** every observation, entity, and evidence row traces back to a
``sources`` row whose ``access_method`` must be ``synthetic | authorized |
public``. The application refuses to ingest from sources marked otherwise at
the connector boundary.

Phase 2 ships the guard itself:

- ``SourceConnector`` — the protocol every Phase-3 connector implements.
- ``SyntheticSourceConnector`` — the only connector shipped (offline-first,
  per ARCHITECTURE.md §1.3).
- ``assert_source_allowed`` — the enforcement point, called at the top of
  every connector fetch and by the ingestion pipeline before any write.
"""
from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import Source

# The locked allow-list (DATABASE.md §2). 'subpoenaed' is research-only and
# must never be ingested from by the application.
ALLOWED_ACCESS_METHODS = ("synthetic", "authorized", "public")


class ForbiddenSourceError(Exception):
    """Raised when a connector tries to ingest from a disallowed source.

    Carries the source name and offending access_method so the API layer can
    return a structured 403 and the audit log can record the attempt.
    """

    def __init__(self, source_name: str, access_method: str) -> None:
        self.source_name = source_name
        self.access_method = access_method
        super().__init__(
            f"Source '{source_name}' has access_method '{access_method}'. "
            f"Ingestion is restricted to {ALLOWED_ACCESS_METHODS} (DATABASE.md §2)."
        )


@runtime_checkable
class SourceConnector(Protocol):
    """Interface for data-source connectors (ARCHITECTURE.md §3.1).

    Implementations fetch raw observations from ONE source. The boundary
    check runs before any fetch — a connector cannot bypass it because the
    pipeline calls ``assert_source_allowed`` again before persisting.
    """

    source_name: str

    def fetch(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return raw observation dicts from the source."""
        ...


class SyntheticSourceConnector:
    """The only connector shipped in Phase 2 (offline synthetic fixtures)."""

    def __init__(self, source_name: str, fixtures: list[dict[str, Any]] | None = None) -> None:
        self.source_name = source_name
        self._fixtures = fixtures or []

    def fetch(self, limit: int | None = None) -> list[dict[str, Any]]:
        data = list(self._fixtures)
        return data[:limit] if limit is not None else data


def assert_source_allowed(source: Source | None, *, source_name: str | None = None) -> Source:
    """Enforce the DATABASE.md §2 boundary for a single source row.

    Raises ForbiddenSourceError when the source is missing, disabled, or its
    access_method is outside the allow-list. Returns the validated source so
    callers can proceed with one DB hit.
    """
    if source is None:
        raise ForbiddenSourceError(source_name or "<unknown>", "missing")
    if not source.enabled:
        raise ForbiddenSourceError(source.name, f"{source.access_method} (disabled)")
    if source.access_method not in ALLOWED_ACCESS_METHODS:
        raise ForbiddenSourceError(source.name, source.access_method)
    return source


def resolve_and_check(session: Session, source_name: str) -> Source:
    """Look up a source by name and enforce the boundary in one call."""
    source = session.execute(
        select(Source).where(Source.name == source_name)
    ).scalar_one_or_none()
    return assert_source_allowed(source, source_name=source_name)


def get_synthetic_connector(
    source_name: str, fixtures: list[dict[str, Any]] | None = None
) -> SyntheticSourceConnector:
    """Factory for the synthetic connector; validates the name shape (defense in depth).

    Synthetic source names must not look like live-network endpoints — the
    offline-first rule (ARCHITECTURE.md §1.3) is enforced at naming level too.
    """
    if re.match(r"^(https?|bolt|tcp)://", source_name or ""):
        raise ForbiddenSourceError(source_name, "synthetic (network endpoint name not allowed)")
    return SyntheticSourceConnector(source_name, fixtures)
