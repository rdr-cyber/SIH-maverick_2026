"""Graph repository: builds and queries the in-process graph.

This repository bridges the relational database (actors, personas,
identifiers, relationships, evidence) and the graph adapter.  It
populates the graph from relational data and serves Cytoscape-ready
payloads for the frontend.

The graph is rebuilt on each request (in local mode) from the source
of truth in SQLite/PostgreSQL.  In production, the graph synchronizer
would keep Neo42 in sync; here we rebuild from relational facts.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.graph import get_graph_backend
from app.models.identity import Actor, Identifier, Persona, Source
from app.models.intel import Evidence, Relationship

log = logging.getLogger(__name__)

# Node colors for Cytoscape styling
NODE_COLORS: dict[str, str] = {
    "ACTOR": "#3d7a8c",
    "PERSONA": "#6b7280",
    "IDENTIFIER": "#8b5cf6",
    "RELATIONSHIP": "#ef4444",
    "EVIDENCE": "#22c55e",
    "SOURCE": "#f59e0b",
}

# Edge colors for Cytoscape styling
EDGE_COLORS: dict[str, str] = {
    "POSSIBLY_SAME_AS": "#ef4444",
    "HAS_EVIDENCE": "#22c55e",
    "USES": "#6b7280",
    "APPEARS_ON": "#3b82f6",
}


class GraphRepository:
    """Builds and queries the evidence graph from relational data."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.graph = get_graph_backend()

    def rebuild_graph(self) -> dict[str, int]:
        """Rebuild the in-process graph from relational data.

        This is the sync step: read all actors, personas, identifiers,
        relationships, and evidence from the database and upsert them
        into the graph adapter.
        """
        self.graph.clear()

        # Load all actors
        actors = {a.id: a for a in self.session.execute(select(Actor)).scalars().all()}
        for a in actors.values():
            self.graph.upsert_node(
                "ACTOR", a.code,
                {
                    "display_name": a.display_name,
                    "risk_level": a.risk_level,
                    "category": a.category,
                    "status": a.status,
                    "confidence": a.attribution_confidence,
                    "postgres_uuid": a.id,
                },
                postgres_uuid=a.id,
            )

        # Load all personas and link to actors
        personas = self.session.execute(
            select(Persona).options(selectinload(Persona.source))
        ).scalars().all()
        for p in personas:
            actor = actors.get(p.actor_id)
            actor_code = actor.code if actor else p.actor_id
            self.graph.upsert_node(
                "PERSONA", f"{actor_code}:{p.name}",
                {
                    "display_name": p.name,
                    "platform": p.platform,
                    "platform_type": p.platform_type,
                    "status": p.status,
                    "postgres_uuid": p.id,
                },
                postgres_uuid=p.id,
            )
            # Edge: Actor → USES → Persona
            if actor:
                self.graph.upsert_edge(
                    "ACTOR", actor.code, "USES",
                    "PERSONA", f"{actor_code}:{p.name}",
                )

        # Load all identifiers and link to personas/actors
        identifiers = self.session.execute(select(Identifier)).scalars().all()
        for i in identifiers:
            actor = actors.get(i.actor_id)
            actor_code = actor.code if actor else i.actor_id
            # Find the persona this identifier belongs to
            persona = None
            for p in personas:
                if p.id == i.persona_id:
                    persona = p
                    break
            persona_key = f"{actor_code}:{persona.name}" if persona else f"{actor_code}:unknown"

            # Create identifier node
            label = i.kind.upper().replace("_", "")
            id_value = i.value if len(i.value) <= 20 else f"{i.value[:12]}…{i.value[-6:]}"
            self.graph.upsert_node(
                label, i.normalized_value,
                {
                    "display_name": id_value,
                    "kind": i.kind,
                    "label": i.label or "",
                    "postgres_uuid": i.id,
                },
                postgres_uuid=i.id,
            )
            # Edge: Persona → HAS → Identifier
            self.graph.upsert_edge(
                "PERSONA", persona_key, "HAS",
                label, i.normalized_value,
            )

        # Load relationships. Deterministic order + curated-code preference:
        # the ingestion pipeline can mint a second POSSIBLY_SAME_AS row for the
        # same actor pair (hash-coded INGESTED:* codes, see ingestion.py).
        # upsert_edge keeps the LAST writer per (source, kind, target), so order
        # non-REL codes first and curated REL-* last — the WHY? panel must show
        # the curated relationship, never depend on row iteration order.
        rels = self.session.execute(
            select(Relationship).order_by(
                Relationship.code.startswith("REL-"),
                Relationship.code,
            )
        ).scalars().all()
        for r in rels:
            from_actor = actors.get(r.from_id)
            to_actor = actors.get(r.to_id)
            if from_actor and to_actor:
                self.graph.upsert_node(
                    "RELATIONSHIP", r.code,
                    {
                        "display_name": r.code,
                        "kind": r.kind,
                        "confidence": r.confidence,
                        "band": r.band,
                        "status": r.status,
                        "explanation": r.explanation or "",
                        "hypothesis_label": r.hypothesis_label or "",
                        "postgres_uuid": r.id,
                    },
                    postgres_uuid=r.id,
                )
                # Edge: Actor → POSSIBLY_SAME_AS → Actor
                # Inference-edge payload per API.md §6 / GRAPH_MODEL.md §3:
                # {confidence, band, status, evidence_ids, explanation, ...}
                self.graph.upsert_edge(
                    "ACTOR", from_actor.code, r.kind,
                    "ACTOR", to_actor.code,
                    {
                        "confidence": r.confidence,
                        "band": r.band,
                        "status": r.status,
                        "code": r.code,
                        "evidence_ids": r.evidence_ids or [],
                        "explanation": r.explanation or "",
                        "scoring_factors": r.scoring_factors or [],
                        "hypothesis_label": r.hypothesis_label or "",
                        "relationship_code": r.code,
                    },
                )

        # Load evidence and link to relationships
        evidence_items = self.session.execute(select(Evidence)).scalars().all()
        for ev in evidence_items:
            self.graph.upsert_node(
                "EVIDENCE", ev.code,
                {
                    "display_name": ev.title,
                    "kind": ev.kind,
                    "strength": ev.strength,
                    "evidence_class": ev.evidence_class,
                    "score_contribution": ev.score_contribution,
                    "postgres_uuid": ev.id,
                },
                postgres_uuid=ev.id,
            )
            # Find the relationship this evidence supports
            for r in rels:
                if r.id == ev.relationship_id:
                    self.graph.upsert_edge(
                        "EVIDENCE", ev.code, "HAS_EVIDENCE",
                        "RELATIONSHIP", r.code,
                        {"score_contribution": ev.score_contribution},
                    )
                    break

        return {
            "actors": len(actors),
            "personas": len(personas),
            "identifiers": len(identifiers),
            "relationships": len(rels),
            "evidence": len(evidence_items),
        }

    def get_cytoscape_data(
        self,
        *,
        depth: int = 2,
        max_nodes: int = 250,
        focus: str | None = None,
    ) -> dict[str, Any]:
        """Return Cytoscape-ready graph data.

        If *focus* is provided (an actor code), center the graph on that
        actor.  Otherwise return the full graph (capped at *max_nodes*).
        """
        # Always rebuild from relational data
        self.rebuild_graph()

        if focus:
            # Find the actor code
            actor = self.session.execute(
                select(Actor).where(Actor.code == focus)
            ).scalar_one_or_none()
            if actor:
                data = self.graph.neighborhood("ACTOR", actor.code, depth=depth, max_nodes=max_nodes)
            else:
                data = {"nodes": [], "edges": []}
        else:
            # Full graph — collect all nodes and edges
            all_nodes = []
            all_edges = []
            for (label, pgkey), props in self.graph._nodes.items():
                all_nodes.append({
                    "data": {
                        "id": f"{label}:{pgkey}",
                        "label": props.get("display_name", pgkey),
                        "group": label.lower(),
                        **{k: v for k, v in props.items() if k != "postgres_uuid"},
                    },
                })
            for fk, rt, tk, eprops in self.graph._edges:
                all_edges.append({
                    "data": {
                        "source": f"{fk[0]}:{fk[1]}",
                        "target": f"{tk[0]}:{tk[1]}",
                        "rel_type": rt,
                        **eprops,
                    },
                })
            data = {"nodes": all_nodes[:max_nodes], "edges": all_edges}

        return data

    def get_node_detail(self, label: str, pgkey: str) -> dict[str, Any] | None:
        """Get detailed properties for a single graph node."""
        self.rebuild_graph()
        return self.graph.get_node(label, pgkey)

    def get_edge_evidence(self, source_id: str, target_id: str) -> list[dict[str, Any]]:
        """Get evidence items for a specific edge (relationship).

        source_id and target_id are in 'LABEL:pgkey' format.
        """
        # Always rebuild from relational data — this request may not be preceded
        # by a GET /graph call, so the in-memory graph can't be assumed populated.
        self.rebuild_graph()

        # Extract the relationship code from the edge properties
        edges = []
        for fk, rt, tk, props in self.graph._edges:
            fk_str = f"{fk[0]}:{fk[1]}"
            tk_str = f"{tk[0]}:{tk[1]}"
            if fk_str == source_id and tk_str == target_id:
                edges.append({"rel_type": rt, **props})

        # If this is a POSSIBLY_SAME_AS edge, find the relationship and its evidence.
        # Returns the full WHY payload: relationship inference metadata (band, status,
        # scoring factors, explanation) plus the evidence chain — GRAPH_MODEL.md §3.
        for edge in edges:
            rel_code = edge.get("relationship_code")
            if rel_code:
                rel = self.session.execute(
                    select(Relationship).where(Relationship.code == rel_code)
                ).scalar_one_or_none()
                if rel:
                    evidence = self.session.execute(
                        select(Evidence).where(Evidence.relationship_id == rel.id)
                    ).scalars().all()
                    return {
                        "relationship": {
                            "code": rel.code,
                            "kind": rel.kind,
                            "confidence": rel.confidence,
                            "band": rel.band,
                            "status": rel.status,
                            "hypothesis_label": rel.hypothesis_label or "",
                            "explanation": rel.explanation or "",
                            "scoring_factors": rel.scoring_factors or [],
                            "evidence_ids": rel.evidence_ids or [],
                            "ruled_out_summary": rel.ruled_out_summary or "",
                            "from_code": edge.get("source", "").split(":", 1)[-1],
                            "to_code": edge.get("target", "").split(":", 1)[-1],
                        },
                        "evidence": [
                            {
                                "id": str(e.id),
                                "code": e.code,
                                "kind": e.kind,
                                "title": e.title,
                                "description": e.description,
                                "strength": e.strength,
                                "evidence_class": e.evidence_class,
                                "score_contribution": e.score_contribution,
                            }
                            for e in evidence
                        ],
                    }
        return {"relationship": None, "evidence": []}
