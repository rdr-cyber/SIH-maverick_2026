"""Graph API endpoint.

Serves Cytoscape-ready graph data for the frontend visualization.
The graph is rebuilt from relational data on each request (in local mode).
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.api.auth import get_current_user
from app.api.deps import DbSession
from app.repositories.graph import GraphRepository

router = APIRouter(
    dependencies=[Depends(get_current_user)],prefix="/graph", tags=["graph"])


@router.get(
    "",
    summary="Get Cytoscape-ready graph data",
)
def get_graph(
    session: DbSession,
    focus: Annotated[Optional[str], Query(description="Actor code to center on")] = None,
    depth: Annotated[int, Query(ge=1, le=4)] = 2,
    max_nodes: Annotated[int, Query(ge=10, le=500)] = 250,
) -> dict:
    """Return graph data in Cytoscape.js format.

    Nodes have: id, label, group (actor/persona/identifier/relationship/evidence)
    Edges have: source, target, rel_type, and optional properties.

    If focus is provided, the graph centers on that actor's neighborhood.
    """
    repo = GraphRepository(session)
    return repo.get_cytoscape_data(focus=focus, depth=depth, max_nodes=max_nodes)


@router.get(
    "/node/{label}/{pgkey}",
    summary="Get detailed properties for a graph node",
)
def get_node(
    session: DbSession,
    label: str,
    pgkey: str,
) -> dict:
    """Return detailed properties for a single graph node."""
    repo = GraphRepository(session)
    node = repo.get_node_detail(label, pgkey)
    if node is None:
        return {"error": "Node not found"}
    return node


@router.get(
    "/edge/evidence",
    summary="Get evidence for a specific edge",
)
def get_edge_evidence(
    session: DbSession,
    source: str = Query(description="Source node ID (LABEL:pgkey)"),
    target: str = Query(description="Target node ID (LABEL:pgkey)"),
) -> dict:
    """Return the full WHY payload for an edge: relationship inference metadata
    (band, status, scoring factors, explanation) plus its evidence chain —
    GRAPH_MODEL.md §3 / API.md §6.
    """
    repo = GraphRepository(session)
    return repo.get_edge_evidence(source, target)
