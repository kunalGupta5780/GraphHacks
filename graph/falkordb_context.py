"""
Real FalkorDB-backed graph context.

Requires a running FalkorDB instance (Docker recommended):

    docker run -p 6379:6379 -d falkordb/falkordb:latest

If the server is unreachable the factory in ``config.py`` falls back to
``InMemoryContext`` automatically, so the agent works anywhere.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    import falkordb  # type: ignore
except ImportError:
    falkordb = None  # type: ignore

from .base import GraphContext, GraphResult, Node, Relationship, Path, PathStep


class FalkorDBContext(GraphContext):
    """Production backend - a real FalkorDB server (Redis module)."""

    def __init__(self, host: str = "localhost", port: int = 6379,
                 graph_name: str = "graphhacks") -> None:
        if falkordb is None:
            raise RuntimeError(
                "falkordb package not installed. Run: pip install falkordb"
            )
        self._host = host
        self._port = port
        self._graph_name = graph_name
        self._client = falkordb.Graph(host, port, graph_name)
        try:
            self._client.query("RETURN 1")
        except Exception:
            raise ConnectionError(
                f"Cannot connect to FalkorDB at {host}:{port}. "
                "Start with: docker run -p 6379:6379 -d falkordb/falkordb:latest"
            )

    @property
    def backend_name(self) -> str:
        return f"FalkorDB ({self._host}:{self._port}/{self._graph_name})"

    # ------------------------------------------------------------------ #
    # Node operations
    # ------------------------------------------------------------------ #

    def add_node(self, label: str, properties: dict, node_id: Optional[str] = None) -> str:
        if node_id:
            query = f"MERGE (n:{label} {{_id: $node_id}}) SET n += $props RETURN id(n)"
            result = self._client.query(query, {"node_id": node_id, "props": properties})
        else:
            props_str = ", ".join(f"{k}: ${k}" for k in properties)
            query = f"CREATE (n:{label} {{{props_str}}}) RETURN id(n)"
            result = self._client.query(query, properties)
        return str(result.result_set[0][0]) if result.result_set else ""

    def find_node(self, label: str, property_name: str, property_value: Any) -> Optional[Node]:
        query = f"MATCH (n:{label}) WHERE n.{property_name} = $val RETURN n"
        result = self._client.query(query, {"val": property_value})
        if not result.result_set:
            return None
        return self._row_to_node(result.result_set[0][0])

    def find_nodes(self, label: str, properties: Optional[dict] = None) -> list[Node]:
        properties = properties or {}
        where_parts = [f"n.{k} = ${k}" for k in properties]
        where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""
        query = f"MATCH (n:{label}){where_clause} RETURN n"
        result = self._client.query(query, properties)
        nodes: list[Node] = []
        for row in result.result_set:
            node = self._row_to_node(row[0])
            if node:
                nodes.append(node)
        return nodes

    # ------------------------------------------------------------------ #
    # Relationship operations
    # ------------------------------------------------------------------ #

    def add_relationship(self, source_id: str, rel_type: str, target_id: str,
                         properties: Optional[dict] = None) -> str:
        properties = properties or {}
        props_str = ", ".join(f"{k}: ${k}" for k in properties) if properties else ""
        rel_clause = f" {{{props_str}}}" if props_str else ""
        query = (
            f"MATCH (s) WHERE id(s) = $src "
            f"MATCH (t) WHERE id(t) = $tgt "
            f"MERGE (s)-[r:{rel_type}{rel_clause}]->(t) "
            f"RETURN id(r)"
        )
        params = {"src": int(source_id), "tgt": int(target_id)}
        params.update(properties)
        result = self._client.query(query, params)
        return str(result.result_set[0][0]) if result.result_set else ""

    # ------------------------------------------------------------------ #
    # Traversal / path queries
    # ------------------------------------------------------------------ #

    def neighbors(self, node_id: str, rel_types: Optional[list[str]] = None,
                  direction: str = "both", max_depth: int = 1) -> list[Node]:
        rel_filter = ""
        if rel_types:
            type_list = "|".join(rel_types)
            if direction == "out":
                rel_filter = f"-[:[{type_list}]]->"
            elif direction == "in":
                rel_filter = f"<-[:[{type_list}]]-"
            else:
                rel_filter = f"-[:[{type_list}]]-"
        else:
            if direction == "out":
                rel_filter = "-->"
            elif direction == "in":
                rel_filter = "<--"
            else:
                rel_filter = "--"

        query = f"MATCH (n){rel_filter}(m) WHERE id(n) = $id RETURN DISTINCT m"
        result = self._client.query(query, {"id": int(node_id)})
        nodes: list[Node] = []
        for row in result.result_set:
            node = self._row_to_node(row[0])
            if node:
                nodes.append(node)
        return nodes

    def shortest_path(self, source_label: str, source_props: dict,
                      target_label: str, target_props: dict,
                      max_hops: int = 10) -> Optional[Path]:
        src_conditions = " AND ".join(f"s.{k} = ${k}" for k in source_props)
        tgt_conditions = " AND ".join(f"t.{k} = ${k}" for k in target_props)
        src_where = f" WHERE {src_conditions}" if source_props else ""
        tgt_where = f" WHERE {tgt_conditions}" if target_props else ""
        query = (
            f"MATCH (s:{source_label}){src_where}, (t:{target_label}){tgt_where} "
            f"MATCH p = shortestPath((s)-[*..{max_hops}]-(t)) RETURN p"
        )
        all_params = {**source_props, **target_props}
        result = self._client.query(query, all_params)
        if not result.result_set:
            return None
        return self._path_from_result(result.result_set[0][0])

    # ------------------------------------------------------------------ #
    # Bulk operations
    # ------------------------------------------------------------------ #

    def delete_graph(self) -> None:
        try:
            self._client.query("MATCH (n) DETACH DELETE n")
        except Exception:
            pass

    def save_snapshot(self) -> dict[str, Any]:
        result = self._client.query("MATCH (n) RETURN count(n) AS count")
        node_count = result.result_set[0][0] if result.result_set else 0
        result = self._client.query("MATCH ()-[r]->() RETURN count(r) AS count")
        edge_count = result.result_set[0][0] if result.result_set else 0
        return {
            "backend": self.backend_name,
            "node_count": int(node_count),
            "edge_count": int(edge_count),
        }

    def get_graph_data(self) -> dict[str, Any]:
        """Return all nodes and edges for visualisation."""
        result = self._client.query("MATCH (n) RETURN n")
        nodes = []
        for row in result.result_set:
            n = self._row_to_node(row[0])
            if n:
                name = n.properties.get("name", n.properties.get("title", n.id))
                nodes.append({
                    "id": n.id,
                    "label": name,
                    "title": name,
                    "labels": n.labels,
                    "properties": n.properties,
                })

        edges = []
        edge_result = self._client.query(
            "MATCH (a)-[r]->(b) RETURN id(a) AS src, type(r) AS rtype, "
            "properties(r) AS props, id(b) AS tgt"
        )
        for row in edge_result.result_set:
            edges.append({
                "from": str(row[0]),
                "to": str(row[3]),
                "type": row[1],
                "label": row[1],
                "title": row[1],
                "arrows": "to",
                "properties": row[2] or {},
            })

        return {"nodes": nodes, "edges": edges, "snapshot": self.save_snapshot()}

    def execute(self, query: str, params: Optional[dict] = None) -> GraphResult:
        params = params or {}
        result = self._client.query(query, params)
        columns = result.header or []
        rows: list[dict[str, Any]] = []
        for row in result.result_set:
            row_dict: dict[str, Any] = {}
            for i, col in enumerate(columns):
                if i < len(row):
                    val = row[i]
                    if hasattr(val, "properties"):
                        row_dict[col] = val.properties
                    elif hasattr(val, "value"):
                        row_dict[col] = val.value
                    else:
                        row_dict[col] = str(val) if val is not None else None
            rows.append(row_dict)
        return GraphResult(
            columns=columns, rows=rows,
            summary=f"{len(rows)} row(s) returned", query=query,
        )

    # ------------------------------------------------------------------ #
    # Graph algorithms
    # ------------------------------------------------------------------ #

    def page_rank(self, top_n: int = 5) -> list[tuple[str, float]]:
        try:
            result = self._client.query(
                "CALL algo.pageRank('Person', 'WORKS_ON', {topN: $top_n}) "
                "YIELD nodeId, score RETURN nodeId, score",
                {"top_n": top_n}
            )
            return [(str(row[0]), float(row[1])) for row in result.result_set]
        except Exception:
            return []

    def connected_components(self) -> list[list[str]]:
        try:
            result = self._client.query(
                "CALL algo.connectedComponents() YIELD nodeId, component RETURN nodeId, component"
            )
            components: dict[int, list[str]] = {}
            for row in result.result_set:
                comp = row[1]
                nid = str(row[0])
                components.setdefault(comp, []).append(nid)
            return list(components.values())
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _row_to_node(self, raw) -> Optional[Node]:
        if raw is None:
            return None
        props = dict(getattr(raw, "properties", {}))
        node_id = props.pop("_id", str(getattr(raw, "id", "")))
        props["_id"] = node_id
        labels = list(getattr(raw, "labels", []))
        return Node(id=node_id, labels=labels, properties=props)

    def _path_from_result(self, raw_path) -> Optional[Path]:
        if raw_path is None:
            return None
        path = Path()
        nodes = getattr(raw_path, "nodes", [])
        edges = list(getattr(raw_path, "edges", []))

        for i, n in enumerate(nodes):
            node = self._row_to_node(n)
            if node is None:
                continue
            rel = None
            if i > 0 and i - 1 < len(edges):
                e = edges[i - 1]
                rel = Relationship(
                    id=str(getattr(e, "id", f"rel_{i}")),
                    type=getattr(e, "type", ""),
                    source=str(getattr(e, "src", "")),
                    target=str(getattr(e, "dst", "")),
                    properties=dict(getattr(e, "properties", {})),
                )
            path.steps.append(PathStep(node=node, relationship=rel))
        return path