"""Ingestion package.

Phase 2 ships the **connector boundary** (``app.ingestion.boundary``): the
DATABASE.md §2 guardrail that refuses any source whose ``access_method`` is
not ``synthetic | authorized | public``. Connectors themselves arrive in
Phase 3.
"""
from .boundary import (
    ALLOWED_ACCESS_METHODS,
    ForbiddenSourceError,
    SourceConnector,
    SyntheticSourceConnector,
    assert_source_allowed,
    get_synthetic_connector,
)

__all__ = [
    "ALLOWED_ACCESS_METHODS",
    "ForbiddenSourceError",
    "SourceConnector",
    "SyntheticSourceConnector",
    "assert_source_allowed",
    "get_synthetic_connector",
]
