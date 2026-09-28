"""Shared audit-event helper — SECURITY.md §6.

Every mutation that matters writes to ``audit_events`` (append-only; no
application code UPDATEs or DELETEs rows there). Actions use the dotted
vocabulary: ``auth.login`` / ``auth.login_failed`` / ``auth.logout`` /
``auth.refresh`` / ``rel.accept`` / ``investigation.create`` / ``scan.tick`` …
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models.ops import AuditEvent

log = logging.getLogger(__name__)


def write_audit(
    session: Session,
    *,
    action: str,
    analyst_id: str | None = None,
    is_system: bool = False,
    resource_type: str | None = None,
    resource_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    note: str | None = None,
) -> None:
    """Append an audit event. Best-effort: audit must never break a request."""
    try:
        session.add(
            AuditEvent(
                analyst_id=analyst_id,
                is_system=is_system,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                before_json=before,
                after_json=after,
                ip=ip,
                user_agent=user_agent[:200] if user_agent else None,
                note=note,
                occurred_at=utcnow(),
            )
        )
        session.flush()
    except Exception:  # pragma: no cover - audit is never load-bearing
        log.exception("failed to write audit event (action=%s)", action)
        session.rollback()
