"""Investigation workspace service.

Business logic for the analyst workflow:
  Create Investigation → Select Target → Explore → Review → Decide → Report

Decisions are NEVER automatic. The correlation engine proposes, the analyst disposes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.intel import Relationship
from app.models.ops import AuditEvent, Investigation
from app.repositories.investigations import (
    add_investigation_note,
    create_investigation,
    decide_relationship,
    get_analyst_by_username,
    get_audit_events,
    get_investigation,
    list_investigations,
    update_investigation_status,
)


@dataclass
class InvestigationOut:
    code: str
    title: str
    description: str | None
    status: str
    lead_analyst: str
    targets: list[str]
    parameters: dict[str, Any]
    relationships: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class AuditEntry:
    id: int
    action: str
    analyst: str
    resource_type: str | None
    before: dict | None
    after: dict | None
    note: str | None
    occurred_at: str


class InvestigationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # List / get
    # ------------------------------------------------------------------

    def list_investigations(self, status: str | None = None) -> list[dict[str, Any]]:
        invs = list_investigations(self.session, status=status)
        return [self._to_dict(inv) for inv in invs]

    def get_investigation(self, code: str) -> dict[str, Any] | None:
        inv = get_investigation(self.session, code)
        if not inv:
            return None
        result = self._to_dict(inv)
        # Attach relationships involving this investigation's targets
        result["relationships"] = self._get_target_relationships(inv)
        return result

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_investigation(
        self,
        *,
        title: str,
        description: str,
        lead_analyst: str,
        targets: list[str] | None = None,
        parameters: dict | None = None,
    ) -> dict[str, Any]:
        analyst = get_analyst_by_username(self.session, lead_analyst)
        if not analyst:
            raise ValueError(f"Analyst '{lead_analyst}' not found")

        code = f"INV-{uuid.uuid4().hex[:8].upper()}"
        inv = create_investigation(
            self.session,
            code=code,
            title=title,
            description=description,
            lead_analyst_id=analyst.id,
            targets=targets or [],
            parameters=parameters or {},
        )
        self.session.commit()
        return self._to_dict(inv)

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def activate(self, code: str, analyst: str) -> dict[str, Any]:
        return self._transition(code, "active", analyst)

    def pause(self, code: str, analyst: str) -> dict[str, Any]:
        return self._transition(code, "paused", analyst)

    def close_investigation(self, code: str, analyst: str) -> dict[str, Any]:
        return self._transition(code, "closed", analyst)

    def _transition(self, code: str, new_status: str, analyst: str) -> dict[str, Any]:
        inv = get_investigation(self.session, code)
        if not inv:
            raise ValueError(f"Investigation '{code}' not found")
        analyst_obj = get_analyst_by_username(self.session, analyst)
        analyst_id = analyst_obj.id if analyst_obj else None
        update_investigation_status(
            self.session, inv, new_status=new_status, analyst_id=analyst_id
        )
        self.session.commit()
        return self._to_dict(inv)

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def add_note(self, code: str, analyst: str, note: str) -> dict[str, Any]:
        inv = get_investigation(self.session, code)
        if not inv:
            raise ValueError(f"Investigation '{code}' not found")
        analyst_obj = get_analyst_by_username(self.session, analyst)
        analyst_id = analyst_obj.id if analyst_obj else None
        add_investigation_note(self.session, inv, note=note, analyst_id=analyst_id)
        self.session.commit()
        return {"ok": True, "code": code}

    # ------------------------------------------------------------------
    # Relationship decision
    # ------------------------------------------------------------------

    def decide_relationship(
        self,
        *,
        relationship_id: str,
        decision: str,
        analyst: str,
        review_note: str | None = None,
    ) -> dict[str, Any]:
        if decision not in ("accepted", "rejected", "uncertain"):
            raise ValueError(f"Invalid decision: {decision}")

        analyst_obj = get_analyst_by_username(self.session, analyst)
        analyst_id = analyst_obj.id if analyst_obj else None

        rel, audit = decide_relationship(
            self.session,
            relationship_id=relationship_id,
            decision=decision,
            analyst_id=analyst_id,
            review_note=review_note,
        )
        self.session.commit()

        # Resolve actor codes
        from app.models.identity import Actor

        actor_a = self.session.get(Actor, rel.from_id)
        actor_b = self.session.get(Actor, rel.to_id)

        return {
            "relationship_code": rel.code,
            "from_actor": actor_a.code if actor_a else rel.from_id,
            "to_actor": actor_b.code if actor_b else rel.to_id,
            "decision": decision,
            "review_note": review_note,
            "audit_id": audit.id,
            "occurred_at": audit.occurred_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def get_audit(
        self,
        *,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        from app.models.ops import Analyst as AnalystModel

        events = get_audit_events(
            self.session,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
        results = []
        for e in events:
            analyst_obj = self.session.get(AnalystModel, e.analyst_id) if e.analyst_id else None
            results.append({
                "id": e.id,
                "action": e.action,
                "analyst": analyst_obj.username if analyst_obj else "system",
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "before": e.before_json,
                "after": e.after_json,
                "note": e.note,
                "occurred_at": e.occurred_at.isoformat(),
            })
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_dict(self, inv: Investigation) -> dict[str, Any]:
        from app.models.ops import Analyst as AnalystModel

        analyst = self.session.get(AnalystModel, inv.lead_analyst_id) if inv.lead_analyst_id else None
        return {
            "code": inv.code,
            "title": inv.title,
            "description": inv.description,
            "status": inv.status,
            "lead_analyst": analyst.username if analyst else "unknown",
            "targets": inv.targets or [],
            "parameters": inv.parameters or {},
            "created_at": inv.created_at.isoformat() if inv.created_at else "",
            "updated_at": inv.updated_at.isoformat() if inv.updated_at else "",
        }

    def _get_target_relationships(self, inv: Investigation) -> list[dict[str, Any]]:
        """Get relationships involving this investigation's target actors."""
        targets = inv.targets or []
        if not targets:
            return []

        from app.models.identity import Actor
        from sqlalchemy import select as sa_select

        actor_map = {}
        for code in targets:
            actor = self.session.execute(
                sa_select(Actor).where(Actor.code == code)
            ).scalar_one_or_none()
            if actor:
                actor_map[actor.id] = actor.code

        if not actor_map:
            return []

        from sqlalchemy import select as sa_select

        stmt = sa_select(Relationship).where(
            Relationship.from_id.in_(actor_map.keys())
            | Relationship.to_id.in_(actor_map.keys())
        )
        rels = list(self.session.execute(stmt).scalars().all())

        results = []
        for rel in rels:
            from_code = actor_map.get(rel.from_id, rel.from_id)
            to_code = actor_map.get(rel.to_id, rel.to_id)
            results.append({
                "code": rel.code,
                "kind": rel.kind,
                "from_actor": from_code,
                "to_actor": to_code,
                "confidence": rel.confidence,
                "band": rel.band,
                "status": rel.status,
                "hypothesis_label": rel.hypothesis_label,
                "review_note": rel.review_note,
            })
        return results
