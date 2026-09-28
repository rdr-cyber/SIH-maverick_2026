"""Graph package — Phase 2 ships the bookkeeping layer only.

Per the roadmap, the Neo4j synchronizer arrives in Phase 5. What exists now:

- ``GraphSyncState`` model (DATABASE.md §10) — the Postgres side of the
  eventual-consistency contract.
- ``mark_pending`` / ``mark_synced`` / ``mark_failed`` — the state-machine
  helpers later phases will call around their MERGE operations.
- ``graph_outbox`` — rows still owed to Neo4j, i.e. what a Phase-5
  synchronizer would replay after an outage (tolerant, idempotent).
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ops_extra import SYNC_STATUSES, GraphSyncState


def _upsert(session: Session, entity_type: str, entity_id: str) -> GraphSyncState:
    row = session.get(GraphSyncState, {"entity_type": entity_type, "entity_id": entity_id})
    if row is None:
        row = GraphSyncState(entity_type=entity_type, entity_id=entity_id)
        session.add(row)
    return row


def mark_pending(session: Session, entity_type: str, entity_id: str) -> None:
    """Flag an entity as owed to the graph index (Phase 5 consumes these)."""
    row = _upsert(session, entity_type, entity_id)
    row.sync_status = "pending"


def mark_synced(session: Session, entity_type: str, entity_id: str) -> None:
    row = _upsert(session, entity_type, entity_id)
    row.sync_status = "synced"
    row.last_error = None


def mark_failed(session: Session, entity_type: str, entity_id: str, error: str) -> None:
    row = _upsert(session, entity_type, entity_id)
    row.sync_status = "failed"
    row.last_error = error[:500]
    row.attempts = (row.attempts or 0) + 1


def graph_outbox(session: Session, limit: int = 100) -> list[GraphSyncState]:
    """Entities whose latest state still needs pushing to Neo4j."""
    stmt = (
        select(GraphSyncState)
        .where(GraphSyncState.sync_status.in_(("pending", "failed")))
        .order_by(GraphSyncState.updated_at.asc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def outbox_depth(session: Session) -> dict[str, int]:
    """Per-status counts — feeds /admin/system health in later phases."""
    rows = session.execute(
        select(GraphSyncState.sync_status, func.count())
        .group_by(GraphSyncState.sync_status)
    ).all()
    counts = {status: 0 for status in SYNC_STATUSES}
    for status_value, n in rows:
        counts[status_value] = n
    return counts
