"""Graph backend adapter layer.

Defines the ``GraphBackend`` protocol that the service layer programs
against, plus two concrete implementations:

* ``InProcessGraph`` — dict-based, used in ``APP_MODE=local``.  No external
  dependencies.  Good enough for the demo and for tests.
* ``Neo4jGraph`` — thin wrapper around the official ``neo4j`` driver,
  selected in ``APP_MODE=production``.  Imported lazily so the driver is
  not required when running locally.

The factory function ``get_graph_backend()`` returns the adapter that
``settings.graph_backend`` points to.  Business logic never imports a
concrete class directly — it depends on the protocol only.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Literal, Protocol, runtime_checkable

from .config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class GraphBackend(Protocol):
    """Minimal contract every graph adapter must satisfy."""

    def upsert_node(
        self,
        label: str,
        pgkey: str,
        properties: dict[str, Any] | None = None,
        *,
        postgres_uuid: str | None = None,
    ) -> None:
        """Create or update a node identified by *label* + *pgkey*."""
        ...

    def upsert_edge(
        self,
        from_label: str,
        from_pgkey: str,
        rel_type: str,
        to_label: str,
        to_pgkey: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create or update a directed edge between two nodes."""
        ...

    def get_node(
        self,
        label: str,
        pgkey: str,
    ) -> dict[str, Any] | None:
        """Return node properties or *None* if absent."""
        ...

    def get_edges(
        self,
        from_label: str,
        from_pgkey: str,
        rel_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return all outgoing edges (optionally filtered by type)."""
        ...

    def neighborhood(
        self,
        label: str,
        pgkey: str,
        *,
        depth: int = 1,
        max_nodes: int = 250,
    ) -> dict[str, Any]:
        """Return a graph payload suitable for Cytoscape rendering.

        Shape::

            {
                "nodes": [{"data": {"id": "...", "label": "...", ...}}],
                "edges": [{"data": {"source": "...", "target": "...", ...}}],
            }
        """
        ...

    def clear(self) -> None:
        """Remove all nodes and edges (used by tests and --reset seeding)."""
        ...

    def node_count(self) -> int:
        """Total nodes in the store."""
        ...

    def edge_count(self) -> int:
        """Total edges in the store."""
        ...


# ---------------------------------------------------------------------------
# In-process implementation (dict-based, local mode)
# ---------------------------------------------------------------------------

class InProcessGraph:
    """Trivial in-memory graph backed by dicts.

    Good enough for the demo and for unit/integration tests.
    This is *not* a graph database — it does not index or optimize
    traversals.  For production, use the Neo4j adapter.
    """

    def __init__(self) -> None:
        # {(label, pgkey): {properties}}
        self._nodes: dict[tuple[str, str], dict[str, Any]] = {}
        # [(from_key, rel_type, to_key, {properties})]
        self._edges: list[
            tuple[tuple[str, str], str, tuple[str, str], dict[str, Any]]
        ] = []

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _node_key(label: str, pgkey: str) -> tuple[str, str]:
        return (label.upper(), pgkey)

    # -- protocol ----------------------------------------------------------

    def upsert_node(
        self,
        label: str,
        pgkey: str,
        properties: dict[str, Any] | None = None,
        *,
        postgres_uuid: str | None = None,
    ) -> None:
        key = self._node_key(label, pgkey)
        props = dict(properties or {})
        if postgres_uuid:
            props["postgres_uuid"] = postgres_uuid
        props.setdefault("pgkey", pgkey)
        existing = self._nodes.get(key)
        if existing is not None:
            existing.update(props)
        else:
            self._nodes[key] = props

    def upsert_edge(
        self,
        from_label: str,
        from_pgkey: str,
        rel_type: str,
        to_label: str,
        to_pgkey: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        from_key = self._node_key(from_label, from_pgkey)
        to_key = self._node_key(to_label, to_pgkey)
        props = dict(properties or {})
        # Idempotent: replace if same triple exists
        for i, (fk, rt, tk, _) in enumerate(self._edges):
            if fk == from_key and rt == rel_type.upper() and tk == to_key:
                self._edges[i] = (from_key, rel_type.upper(), to_key, props)
                return
        self._edges.append(
            (from_key, rel_type.upper(), to_key, props)
        )

    def get_node(
        self,
        label: str,
        pgkey: str,
    ) -> dict[str, Any] | None:
        return self._nodes.get(self._node_key(label, pgkey))

    def get_edges(
        self,
        from_label: str,
        from_pgkey: str,
        rel_type: str | None = None,
    ) -> list[dict[str, Any]]:
        from_key = self._node_key(from_label, from_pgkey)
        results: list[dict[str, Any]] = []
        for fk, rt, tk, props in self._edges:
            if fk == from_key and (rel_type is None or rt == rel_type.upper()):
                to_node = self._nodes.get(tk)
                results.append({
                    "rel_type": rt,
                    "to_label": tk[0],
                    "to_pgkey": tk[1],
                    "properties": props,
                    "to_properties": to_node or {},
                })
        return results

    def neighborhood(
        self,
        label: str,
        pgkey: str,
        *,
        depth: int = 1,
        max_nodes: int = 250,
    ) -> dict[str, Any]:
        """BFS expansion up to *depth* hops, capped at *max_nodes*."""
        visited: set[tuple[str, str]] = set()
        nodes_out: list[dict[str, Any]] = []
        edges_out: list[dict[str, Any]] = []
        queue: list[tuple[str, str, int]] = [
            (self._node_key(label, pgkey)[0], pgkey, 0)
        ]

        while queue and len(nodes_out) < max_nodes:
            cur_label, cur_pgkey, cur_depth = queue.pop(0)
            cur_key = (cur_label.upper(), cur_pgkey)
            if cur_key in visited:
                continue
            visited.add(cur_key)
            node_props = self._nodes.get(cur_key, {})
            nodes_out.append({
                "data": {
                    "id": f"{cur_label}:{cur_pgkey}",
                    "label": cur_label,
                    "pgkey": cur_pgkey,
                    **{
                        k: v
                        for k, v in node_props.items()
                        if k not in ("postgres_uuid",)
                    },
                },
            })
            if cur_depth >= depth:
                continue
            # Outgoing
            for fk, rt, tk, eprops in self._edges:
                if fk == cur_key and tk not in visited:
                    edges_out.append({
                        "data": {
                            "source": f"{fk[0]}:{fk[1]}",
                            "target": f"{tk[0]}:{tk[1]}",
                            "rel_type": rt,
                            **eprops,
                        },
                    })
                    queue.append((tk[0], tk[1], cur_depth + 1))
            # Incoming
            for fk, rt, tk, eprops in self._edges:
                if tk == cur_key and fk not in visited:
                    edges_out.append({
                        "data": {
                            "source": f"{fk[0]}:{fk[1]}",
                            "target": f"{tk[0]}:{tk[1]}",
                            "rel_type": rt,
                            **eprops,
                        },
                    })
                    queue.append((fk[0], fk[1], cur_depth + 1))

        return {"nodes": nodes_out, "edges": edges_out}

    def clear(self) -> None:
        self._nodes.clear()
        self._edges.clear()

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)


# ---------------------------------------------------------------------------
# Neo4j implementation (production mode) — stub with import guard
# ---------------------------------------------------------------------------

def _sanitize_cypher_label(label: str) -> str:
    """Allow only alphanumeric and underscore in Neo4j labels.

    This prevents Cypher injection through node labels, even though
    labels in this codebase are controlled by the application.
    """
    import re
    return re.sub(r'[^a-zA-Z0-9_]', '', label) or 'UNKNOWN'


def _sanitize_cypher_rel_type(rel_type: str) -> str:
    """Allow only alphanumeric and underscore in relationship types."""
    import re
    return re.sub(r'[^a-zA-Z0-9_]', '', rel_type) or 'UNKNOWN'


class Neo4jGraph:
    """Neo4j-backed graph adapter.

    Requires the ``neo4j`` Python driver (``pip install neo4j``).
    The driver connection is established lazily on first use.

    This is a **stub** for Milestone 3.  The full implementation will use
    parameterized Cypher MERGE statements following the contract in
    ``docs/schemas/neo4j_schema.cypher``.
    """

    def __init__(self) -> None:
        self._driver: Any = None

    def _connect(self) -> Any:
        if self._driver is not None:
            return self._driver
        try:
            from neo4j import GraphDatabase  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError(
                "Neo4j driver not installed.  "
                "Run: pip install neo4j"
            )
        assert settings.neo4j_uri is not None
        assert settings.neo4j_user is not None
        assert settings.neo4j_password is not None
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        log.info("neo4j driver connected to %s", settings.neo4j_uri)
        return self._driver

    def upsert_node(
        self,
        label: str,
        pgkey: str,
        properties: dict[str, Any] | None = None,
        *,
        postgres_uuid: str | None = None,
    ) -> None:
        safe_label = _sanitize_cypher_label(label)
        props = dict(properties or {})
        props["pgkey"] = pgkey
        if postgres_uuid:
            props["postgres_uuid"] = postgres_uuid
        driver = self._connect()
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                f"MERGE (n:{safe_label} {{pgkey: $pgkey}}) SET n += $props",
                pgkey=pgkey,
                props=props,
            )

    def upsert_edge(
        self,
        from_label: str,
        from_pgkey: str,
        rel_type: str,
        to_label: str,
        to_pgkey: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        safe_from = _sanitize_cypher_label(from_label)
        safe_to = _sanitize_cypher_label(to_label)
        safe_rel = _sanitize_cypher_rel_type(rel_type)
        props = dict(properties or {})
        driver = self._connect()
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                f"""
                MATCH (a:{safe_from} {{pgkey: $from_pgkey}})
                MATCH (b:{safe_to} {{pgkey: $to_pgkey}})
                MERGE (a)-[r:{safe_rel}]->(b)
                SET r += $props
                """,
                from_pgkey=from_pgkey,
                to_pgkey=to_pgkey,
                props=props,
            )

    def get_node(
        self,
        label: str,
        pgkey: str,
    ) -> dict[str, Any] | None:
        safe_label = _sanitize_cypher_label(label)
        driver = self._connect()
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(
                f"MATCH (n:{safe_label} {{pgkey: $pgkey}}) RETURN n",
                pgkey=pgkey,
            )
            record = result.single()
            if record is None:
                return None
            return dict(record["n"])

    def get_edges(
        self,
        from_label: str,
        from_pgkey: str,
        rel_type: str | None = None,
    ) -> list[dict[str, Any]]:
        safe_from = _sanitize_cypher_label(from_label)
        rel_clause = f":{_sanitize_cypher_rel_type(rel_type)}" if rel_type else ""
        driver = self._connect()
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(
                f"""
                MATCH (a:{safe_from} {{pgkey: $from_pgkey}})-[r{rel_clause}]->(b)
                RETURN type(r) AS rel_type, labels(b)[0] AS to_label,
                       b.pgkey AS to_pgkey, properties(r) AS props
                """,
                from_pgkey=from_pgkey,
            )
            return [dict(record) for record in result]

    def neighborhood(
        self,
        label: str,
        pgkey: str,
        *,
        depth: int = 1,
        max_nodes: int = 250,
    ) -> dict[str, Any]:
        safe_label = _sanitize_cypher_label(label)
        driver = self._connect()
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run(
                f"""
                MATCH path = (n:{safe_label} {{pgkey: $pgkey}})-[*0..{depth}]-(m)
                WITH nodes(path) AS ns, relationships(path) AS rs
                UNWIND ns AS node
                WITH COLLECT(DISTINCT node) AS node_list
                UNWIND node_list AS nd
                WITH node_list, nd, CASE WHEN nd IS NULL THEN 0 ELSE 1 END AS _
                RETURN node_list
                LIMIT $limit
                """,
                pgkey=pgkey,
                limit=max_nodes,
            )
            # Stub: full implementation in Milestone 3
            return {"nodes": [], "edges": []}

    def clear(self) -> None:
        driver = self._connect()
        with driver.session(database=settings.neo4j_database) as session:
            session.run("MATCH (n) DETACH DELETE n")

    def node_count(self) -> int:
        driver = self._connect()
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run("MATCH (n) RETURN count(n) AS cnt")
            return result.single()["cnt"]

    def edge_count(self) -> int:
        driver = self._connect()
        with driver.session(database=settings.neo4j_database) as session:
            result = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            return result.single()["cnt"]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_graph_instance: GraphBackend | None = None


def get_graph_backend() -> GraphBackend:
    """Return the configured graph adapter (singleton per process)."""
    global _graph_instance
    if _graph_instance is not None:
        return _graph_instance

    backend = settings.graph_backend
    if backend == "neo4j":
        _graph_instance = Neo4jGraph()
        log.info("graph adapter: neo4j")
    else:
        _graph_instance = InProcessGraph()
        log.info("graph adapter: inprocess")

    return _graph_instance


def reset_graph_backend() -> None:
    """Reset singleton — used by tests."""
    global _graph_instance
    if _graph_instance is not None and hasattr(_graph_instance, "clear"):
        _graph_instance.clear()
    _graph_instance = None
