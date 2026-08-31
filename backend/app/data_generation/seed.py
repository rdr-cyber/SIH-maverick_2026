"""Idempotent loader for the synthetic catalogue.

Re-running the seed updates existing rows rather than duplicating them, so
``seed_database()`` is safe to call on every startup. Set
``SEED_ON_STARTUP=false`` to disable, or pass ``reset=True`` to rebuild the
tables from scratch.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, reset_db
from app.core.security import hash_password
from app.models.identity import Actor, Identifier, Persona, Source
from app.models.intel import Evidence, Relationship, TimelineEvent
from app.models.ops import Analyst, Investigation, AuditEvent
from app.services.normalization import normalize_handle, normalize_identifier

from .catalog import ACTORS, ANALYSTS, EVIDENCE, INVESTIGATIONS, RELATIONSHIPS, SOURCES, TIMELINE_EVENTS

log = logging.getLogger(__name__)


def _dt(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO date or datetime string into naive UTC."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=None)


def _upsert_sources(session: Session) -> dict[str, Source]:
    existing = {s.name: s for s in session.execute(select(Source)).scalars()}
    for spec in SOURCES:
        row = existing.get(spec["name"])
        if row is None:
            row = Source(name=spec["name"])
            session.add(row)
            existing[spec["name"]] = row
        row.kind = spec["kind"]
        row.reliability = spec["reliability"]
        row.description = spec.get("description")
        row.access_method = spec.get("access_method", "synthetic")
        row.enabled = True
        row.last_scanned_at = _dt(spec.get("last_scanned_at"))
    session.flush()
    return existing


def _upsert_identifier(
    session: Session,
    spec: dict[str, Any],
    *,
    actor: Actor,
    persona: Persona,
    source: Source,
    index: dict[tuple[str | None, str, str], Identifier],
) -> None:
    normalized = normalize_identifier(spec["kind"], spec["value"])
    key = (persona.id, spec["kind"], normalized)
    row = index.get(key)
    if row is None:
        row = Identifier(kind=spec["kind"], normalized_value=normalized)
        session.add(row)
        index[key] = row
    row.actor_id = actor.id
    row.persona_id = persona.id
    row.source_id = source.id
    row.value = spec["value"]
    row.label = spec.get("label")
    row.attributes = dict(spec.get("attributes") or {})
    row.first_seen = persona.first_seen
    row.last_seen = persona.last_seen


def _upsert_persona(
    session: Session,
    spec: dict[str, Any],
    *,
    actor: Actor,
    sources: dict[str, Source],
    persona_index: dict[tuple[str, str], Persona],
    identifier_index: dict[tuple[str | None, str, str], Identifier],
) -> None:
    normalized = normalize_handle(spec["name"])
    key = (normalized, spec["platform"])
    row = persona_index.get(key)
    if row is None:
        row = Persona(normalized_name=normalized, platform=spec["platform"])
        session.add(row)
        persona_index[key] = row

    source = sources.get(spec["platform"])
    if source is None:
        raise KeyError(
            f"persona '{spec['name']}' references platform '{spec['platform']}' "
            "which is not declared in catalog.SOURCES"
        )
    row.actor_id = actor.id
    row.source_id = source.id
    row.name = spec["name"]
    row.platform_type = spec["platform_type"]
    row.status = spec["status"]
    row.is_primary = spec["is_primary"]
    row.reputation = spec.get("reputation")
    row.attributes = dict(spec.get("attributes") or {})
    row.first_seen = _dt(spec.get("first_seen"))
    row.last_seen = _dt(spec.get("last_seen"))
    session.flush()

    for ident in spec["identifiers"]:
        _upsert_identifier(
            session, ident, actor=actor, persona=row, source=source, index=identifier_index
        )


def seed_database(*, reset: bool = False, session: Optional[Session] = None) -> dict[str, int]:
    """Load the synthetic catalogue. Returns row counts per table."""
    if reset:
        reset_db()

    owns_session = session is None
    db = session or SessionLocal()
    try:
        sources = _upsert_sources(db)
        actor_index = {a.code: a for a in db.execute(select(Actor)).scalars()}
        persona_index = {
            (p.normalized_name, p.platform): p for p in db.execute(select(Persona)).scalars()
        }
        identifier_index = {
            (i.persona_id, i.kind, i.normalized_value): i
            for i in db.execute(select(Identifier)).scalars()
        }

        for spec in ACTORS:
            actor = actor_index.get(spec["code"])
            if actor is None:
                actor = Actor(code=spec["code"])
                db.add(actor)
                actor_index[spec["code"]] = actor
            actor.display_name = spec["display_name"]
            actor.summary = spec.get("summary")
            actor.status = spec["status"]
            actor.risk_level = spec["risk_level"]
            actor.category = spec["category"]
            actor.attribution_confidence = float(spec["attribution_confidence"])
            actor.attributes = dict(spec.get("attributes") or {})
            actor.first_seen = _dt(spec.get("first_seen"))
            actor.last_seen = _dt(spec.get("last_seen"))
            actor.last_scan_at = _dt(spec.get("last_scan_at"))
            primary = sources.get(spec.get("primary_source", ""))
            actor.primary_source_id = primary.id if primary else None
            db.flush()

            for persona_spec in spec["personas"]:
                _upsert_persona(
                    db,
                    persona_spec,
                    actor=actor,
                    sources=sources,
                    persona_index=persona_index,
                    identifier_index=identifier_index,
                )

        # --- relationships ----------------------------------------------------
        rel_index = {r.code: r for r in db.execute(select(Relationship)).scalars()}
        for spec in RELATIONSHIPS:
            row = rel_index.get(spec["code"])
            if row is None:
                row = Relationship(code=spec["code"])
                db.add(row)
                rel_index[spec["code"]] = row
            row.kind = spec["kind"]
            row.from_type = spec["from_type"]
            row.to_type = spec["to_type"]
            row.confidence = float(spec["confidence"])
            row.band = spec["band"]
            row.status = spec["status"]
            row.engine_ref = spec.get("engine_ref")
            row.hypothesis_label = spec.get("hypothesis_label")
            row.explanation = spec.get("explanation")
            row.scoring_factors = spec.get("scoring_factors", [])
            row.first_seen = _dt(spec.get("first_seen"))
            row.last_seen = _dt(spec.get("last_seen"))
            row.reviewed_by = spec.get("reviewed_by")
            row.review_note = spec.get("review_note")
            if spec.get("reviewed_by"):
                row.reviewed_at = _dt(spec.get("last_seen"))
            # Resolve from_id / to_id from actor codes
            from_actor = actor_index.get(spec["from_code"])
            to_actor = actor_index.get(spec["to_code"])
            if from_actor:
                row.from_id = from_actor.id
            if to_actor:
                row.to_id = to_actor.id
        db.flush()

        # --- recompute relationship confidence from engines -----------------
        # The confidence engine is the single source of truth for RCS.
        # We recompute after all actors and identifiers are loaded so that
        # the stored score matches what the API serves at runtime.
        try:
            from app.services.confidence import ConfidenceEngine
            ce = ConfidenceEngine(db)
            for spec in RELATIONSHIPS:
                if spec.get("kind") == "POSSIBLY_SAME_AS":
                    row = rel_index.get(spec["code"])
                    if row and row.from_id and row.to_id:
                        from_actor = actor_index.get(spec["from_code"])
                        to_actor = actor_index.get(spec["to_code"])
                        if from_actor and to_actor:
                            cr = ce.compute_confidence(from_actor.code, to_actor.code)
                            row.confidence = cr.score
                            row.band = cr.band.lower()
            db.flush()
        except Exception as exc:
            log.warning("confidence recomputation skipped: %s", exc)

        # --- evidence ---------------------------------------------------------
        ev_index = {e.code: e for e in db.execute(select(Evidence)).scalars()}
        for spec in EVIDENCE:
            row = ev_index.get(spec["code"])
            if row is None:
                row = Evidence(code=spec["code"])
                db.add(row)
                ev_index[spec["code"]] = row
            row.kind = spec["kind"]
            row.title = spec["title"]
            row.description = spec["description"]
            row.strength = spec["strength"]
            row.evidence_class = spec["evidence_class"]
            row.score_contribution = float(spec["score_contribution"])
            row.details = spec.get("details", {})
            # Link to relationship
            rel_code = spec.get("relationship_code")
            if rel_code and rel_code in rel_index:
                row.relationship_id = rel_index[rel_code].id
        db.flush()

        # --- analysts --------------------------------------------------------
        analyst_index = {a.username: a for a in db.execute(select(Analyst)).scalars()}
        for spec in ANALYSTS:
            row = analyst_index.get(spec["username"])
            if row is None:
                row = Analyst(username=spec["username"])
                db.add(row)
                analyst_index[spec["username"]] = row
            row.full_name = spec["full_name"]
            row.email = spec["email"]
            row.password_hash = hash_password(spec["password"])
            row.role = spec["role"]
            row.is_active = True
        db.flush()

        # --- investigations ---------------------------------------------------
        inv_index = {i.code: i for i in db.execute(select(Investigation)).scalars()}
        for spec in INVESTIGATIONS:
            row = inv_index.get(spec["code"])
            if row is None:
                row = Investigation(code=spec["code"])
                db.add(row)
                inv_index[spec["code"]] = row
            row.title = spec["title"]
            row.description = spec.get("description")
            row.status = spec["status"]
            row.targets = spec.get("targets", [])
            row.parameters = spec.get("parameters", {})
            lead = analyst_index.get(spec.get("lead_analyst"))
            if lead:
                row.lead_analyst_id = lead.id
        db.flush()

        # --- timeline events --------------------------------------------------
        # Dedup by (kind, title, occurred_at) to make seed idempotent.
        existing_events = {
            (e.kind, e.title, e.occurred_at): e
            for e in db.execute(select(TimelineEvent)).scalars()
        }
        for spec in TIMELINE_EVENTS:
            actor_code = spec.get("actor_code")
            actor_id = actor_index[actor_code].id if actor_code and actor_code in actor_index else None
            occurred = _dt(spec["occurred_at"])
            key = (spec["kind"], spec["title"], occurred)
            if key not in existing_events:
                evt = TimelineEvent(
                    kind=spec["kind"],
                    actor_id=actor_id,
                    title=spec["title"],
                    detail=spec.get("detail"),
                    occurred_at=occurred,
                )
                db.add(evt)
        db.flush()

        db.commit()
        counts = {
            "sources": len(sources),
            "actors": len(actor_index),
            "personas": len(persona_index),
            "identifiers": len(identifier_index),
            "relationships": len(rel_index),
            "evidence": len(ev_index),
            "analysts": len(analyst_index),
            "investigations": len(inv_index),
            "timeline_events": len(TIMELINE_EVENTS),
        }
        log.info("synthetic catalogue loaded: %s", counts)
        return counts
    finally:
        if owns_session:
            db.close()


def _main() -> None:
    """CLI: ``python -m app.data_generation.seed [--reset]``."""
    import argparse

    from app.core.database import init_db
    from app.core.logging import configure_logging

    parser = argparse.ArgumentParser(description="Load the SHADOWGRAPH synthetic catalogue.")
    parser.add_argument(
        "--reset", action="store_true", help="drop and recreate all tables before seeding"
    )
    args = parser.parse_args()

    configure_logging()
    init_db()
    counts = seed_database(reset=args.reset)
    for table, count in counts.items():
        print(f"{table:<14} {count}")


if __name__ == "__main__":
    _main()
