"""Map API endpoint.

Serves geolocated actors as map pins plus the relationship lines between
co-located actors — the same Relationship rows that power the network
graph (GRAPH_MODEL.md §3), so the map and the graph tell one story.
Actors without geolocation are excluded; roles (victim / suspect /
witness / person_of_interest) come from ``actors.investigation_role``.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.auth import get_current_user
from app.api.deps import DbSession
from app.models.identity import Actor
from app.models.intel import Relationship

router = APIRouter(dependencies=[Depends(get_current_user)], prefix="/map", tags=["map"])


@router.get(
    "",
    summary="Get map pins (geolocated actors) and relationship lines",
)
def get_map(session: DbSession) -> dict[str, Any]:
    """Return geolocated actors and the relationship edges between them.

    Response shape::

        {
          "pins":  [{code, display_name, lat, lng, label, role,
                     risk_level, category, status, confidence}],
          "edges": [{code, kind, from_code, to_code, confidence,
                     band, status, hypothesis_label}],
          "roles": {role: count},   # for legend badges
          "unlocated": [actor codes with no geo]  # transparency about sparsity
        }
    """
    actors = session.execute(
        select(Actor).where(Actor.geo_lat.is_not(None), Actor.geo_lng.is_not(None))
    ).scalars().all()
    all_actors = session.execute(select(Actor)).scalars().all()

    by_id = {a.id: a for a in actors}
    pins = [
        {
            "code": a.code,
            "display_name": a.display_name,
            "lat": a.geo_lat,
            "lng": a.geo_lng,
            "label": a.geo_label,
            "role": a.investigation_role,
            "risk_level": a.risk_level,
            "category": a.category,
            "status": a.status,
            "confidence": a.attribution_confidence,
        }
        for a in actors
    ]

    # Relationship lines: only rows whose BOTH endpoints are geolocated.
    rels = session.execute(select(Relationship)).scalars().all()
    edges = []
    for r in rels:
        f = by_id.get(r.from_id)
        t = by_id.get(r.to_id)
        if f is None or t is None:
            continue
        edges.append(
            {
                "code": r.code,
                "kind": r.kind,
                "from_code": f.code,
                "to_code": t.code,
                "confidence": r.confidence,
                "band": r.band,
                "status": r.status,
                "hypothesis_label": r.hypothesis_label or "",
            }
        )

    roles: dict[str, int] = {}
    for a in all_actors:
        if a.investigation_role:
            roles[a.investigation_role] = roles.get(a.investigation_role, 0) + 1

    located_codes = {a.code for a in actors}
    unlocated = sorted(a.code for a in all_actors if a.code not in located_codes)

    return {"pins": pins, "edges": edges, "roles": roles, "unlocated": unlocated}
