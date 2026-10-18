"""
In-memory graph context – a NetworkX-backed implementation of the
``GraphContext`` interface.

This backend lets the agent run **without** a live FalkorDB server / Docker
stack.  It understands a pragmatic subset of Cypher so that the same queries
work in production (FalkorDB) and in development (in-memory).

When both backends are available the agent automatically prefers FalkorDB.
"""

from __future__ import annotations

import re
import json
import uuid
import networkx as nx
from typing import Any, Optional

from .base import GraphContext, GraphResult, Node, Relationship, Path, PathStep


def _safe_str(v: Any) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True)
    return str(v)


# --------------------------------------------------------------------------- #
# Core implementation
# --------------------------------------------------------------------------- #

class InMemoryContext(GraphContext):
    """NetworkX-backed graph that speaks a subset of Cypher."""

    def __init__(self) -> None:
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self._node_counter: int = 0
        self._rel_counter: int = 0
        self._index: dict[tuple[str, str, str], set[str]] = {}

    @property
    def backend_name(self) -> str:
        return "InMemory (NetworkX fallback)"

    @property
    def graph(self) -> nx.MultiDiGraph:
        return self._graph

    def add_node(self, label: str, properties: dict, node_id: Optional[str] = None) -> str:
        nid = node_id or f"n{self._node_counter}"
        self._node_counter += 1

        if self._graph.has_node(nid):
            existing = self._graph.nodes[nid]
            existing["props"].update(properties)
            labels = existing.get("labels", [])
            if label not in labels:
                labels.append(label)
            existing["labels"] = labels
        else:
            self._graph.add_node(nid, labels=[label], props=dict(properties))

        for k, v in properties.items():
            key = (label, k, _safe_str(v))
            self._index.setdefault(key, set()).add(nid)
            for other_label in self._graph.nodes[nid].get("labels", []):
                if other_label != label:
                    self._index.setdefault((other_label, k, _safe_str(v)), set()).add(nid)
        return nid

    def find_node(self, label: str, property_name: str, property_value: Any) -> Optional[Node]:
        results = self.find_nodes(label, {property_name: property_value})
        return results[0] if results else None

    def find_nodes(self, label: str, properties: Optional[dict] = None) -> list[Node]:
        properties = properties or {}
        candidates: set[str] = set()

        if properties:
            first_key, first_val = next(iter(properties.items()))
            idx_key = (label, first_key, _safe_str(first_val))
            candidates = self._index.get(idx_key, set())
            filtered: set[str] = set()
            for nid in candidates:
                props = self._graph.nodes[nid]["props"]
                if all(props.get(k) == v for k, v in properties.items()):
                    filtered.add(nid)
            candidates = filtered
        else:
            candidates = {
                nid for nid, data in self._graph.nodes(data=True)
                if label in data.get("labels", [])
            }

        result: list[Node] = []
        for nid in sorted(candidates):
            data = self._graph.nodes[nid]
            props = dict(data["props"])
            props["_id"] = nid
            result.append(Node(id=nid, labels=list(data["labels"]), properties=props))
        return result

    def add_relationship(self, source_id: str, rel_type: str, target_id: str, properties: Optional[dict] = None) -> str:
        rel_id = f"r{self._rel_counter}"
        self._rel_counter += 1
        properties = properties or {}
        properties["_rel_id"] = rel_id
        self._graph.add_edge(source_id, target_id, key=rel_id, rel_type=rel_type, props=properties)
        return rel_id

    def neighbors(self, node_id: str, rel_types: Optional[list[str]] = None,
                  direction: str = "both", max_depth: int = 1) -> list[Node]:
        result: list[Node] = []
        seen: set[str] = set()

        if direction in ("both", "out"):
            for src, tgt, data in self._graph.out_edges(node_id, data=True):
                if rel_types and data.get("rel_type") not in rel_types:
                    continue
                if tgt not in seen:
                    seen.add(tgt)
                    ndata = self._graph.nodes[tgt]
                    props = dict(ndata["props"])
                    props["_id"] = tgt
                    result.append(Node(id=tgt, labels=list(ndata["labels"]), properties=props))

        if direction in ("both", "in"):
            for src, tgt, data in self._graph.in_edges(node_id, data=True):
                if rel_types and data.get("rel_type") not in rel_types:
                    continue
                if src not in seen:
                    seen.add(src)
                    ndata = self._graph.nodes[src]
                    props = dict(ndata["props"])
                    props["_id"] = src
                    result.append(Node(id=src, labels=list(ndata["labels"]), properties=props))
        return result

    def shortest_path(self, source_label: str, source_props: dict,
                      target_label: str, target_props: dict,
                      max_hops: int = 10) -> Optional[Path]:
        source_node = target_node = None
        if source_props:
            fk, fv = next(iter(source_props.items()))
            source_node = self.find_node(source_label, fk, fv)
        if target_props:
            fk, fv = next(iter(target_props.items()))
            target_node = self.find_node(target_label, fk, fv)

        if not source_node or not target_node:
            return None

        try:
            path_nodes = nx.shortest_path(self._graph, source=source_node.id, target=target_node.id)
        except nx.NetworkXNoPath:
            return None

        path = Path()
        for i, nid in enumerate(path_nodes):
            ndata = self._graph.nodes[nid]
            props = dict(ndata["props"])
            props["_id"] = nid
            node = Node(id=nid, labels=list(ndata["labels"]), properties=props)
            rel = None
            if i > 0:
                edge_data = self._graph.get_edge_data(path_nodes[i - 1], nid)
                if edge_data:
                    first_key = next(iter(edge_data))
                    edata = edge_data[first_key]
                    rel = Relationship(
                        id=edata.get("props", {}).get("_rel_id", f"rel_{i}"),
                        type=edata.get("rel_type", ""),
                        source=path_nodes[i - 1], target=nid,
                        properties=dict(edata.get("props", {})),
                    )
            path.steps.append(PathStep(node=node, relationship=rel))
        return path

    def delete_graph(self) -> None:
        self._graph.clear()
        self._index.clear()
        self._node_counter = 0
        self._rel_counter = 0

    def save_snapshot(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for _, data in self._graph.nodes(data=True):
            for label in data.get("labels", []):
                counts[label] = counts.get(label, 0) + 1
        return {
            "backend": self.backend_name,
            "node_count": self._graph.number_of_nodes(),
            "edge_count": self._graph.number_of_edges(),
            "label_counts": counts,
        }

    def get_graph_data(self) -> dict[str, Any]:
        """Return all nodes and edges for visualisation."""
        nodes = []
        for nid, data in self._graph.nodes(data=True):
            labels = data.get("labels", [])
            props = data.get("props", {})
            name = props.get("name", props.get("title", nid))
            nodes.append({
                "id": nid,
                "label": name,
                "title": name,
                "labels": labels,
                "properties": props,
            })

        edges = []
        for src, tgt, _key, data in self._graph.edges(data=True, keys=True):
            rel_type = data.get("rel_type", "")
            edges.append({
                "from": src,
                "to": tgt,
                "type": rel_type,
                "label": rel_type,
                "title": rel_type,
                "arrows": "to",
                "properties": data.get("props", {}),
            })

        return {"nodes": nodes, "edges": edges, "snapshot": self.save_snapshot()}

    def execute(self, query: str, params: Optional[dict] = None) -> GraphResult:
        """Execute a Cypher-like query (pragmatic subset)."""
        params = params or {}
        query_stripped = query.strip().rstrip(";").strip()
        upper = query_stripped.upper()

        if upper.startswith("CREATE"):
            return self._handle_create(query_stripped, params)
        elif upper.startswith("MERGE"):
            return self._handle_merge(query_stripped, params)
        elif upper.startswith("SET"):
            return self._handle_set(query_stripped, params)
        elif upper.startswith("DELETE"):
            return self._handle_delete(query_stripped, params)
        elif upper.startswith("MATCH"):
            return self._handle_match(query_stripped, params)
        else:
            return GraphResult(
                columns=[], rows=[],
                summary=f"Unsupported query type: {query_stripped[:50]}...",
                query=query,
            )

    # ------------------------------------------------------------------ #
    # Query handler: MATCH
    # ------------------------------------------------------------------ #

    def _handle_match(self, query: str, params: dict) -> GraphResult:
        return_clause = query.upper().find("RETURN")
        if return_clause == -1:
            return GraphResult(columns=[], rows=[], summary="No RETURN clause", query=query)

        match_part = query[:return_clause].strip()
        return_part = query[return_clause:].strip()
        match_body = match_part[len("MATCH"):].strip()
        
        # Extract WHERE clause from pattern body
        where_clause = ""
        where_pattern = re.search(r'\bWHERE\s+(.+?)(?:\)\s*-\[|\)-\s*-\[|\)-\s*\()', match_body, re.IGNORECASE | re.DOTALL)
        if not where_pattern:
            where_pattern = re.search(r'\bWHERE\s+(.+)$', match_body, re.IGNORECASE | re.DOTALL)
        if where_pattern:
            where_clause = where_pattern.group(1).strip()
            match_body = match_body[:where_pattern.start()].strip()

        # Check for shortestPath
        if "shortestpath" in match_body.lower():
            return self._handle_shortest_path(match_body, return_part, params)

        # Parse the pattern
        pattern = self._parse_pattern(match_body)
        if pattern is None:
            return GraphResult(columns=[], rows=[], summary="Could not parse pattern", query=query)

        s_label, s_var, s_p, rel_type, t_label, t_var, t_p, direction = pattern
        source_nodes = self._match_nodes(s_label, s_p, params)
        target_nodes = self._match_nodes(t_label or "", t_p, params)

        if not target_nodes:
            # Single-node pattern (e.g., MATCH (n) WHERE ...)
            if not source_nodes:
                return GraphResult(columns=[], rows=[], summary="No matching nodes found", query=query)
            filtered = self._filter_where(source_nodes, where_clause, params)
            formatted = self._process_return([n.properties for n in filtered], return_part, filtered[0] if filtered else None)
            return GraphResult(columns=formatted["columns"], rows=formatted["rows"],
                              summary=f"Found {len(formatted['rows'])} result(s)", query=query)
        if not source_nodes or not target_nodes:
            all_nodes = source_nodes + target_nodes
            if not all_nodes:
                return GraphResult(columns=[], rows=[], summary="No matching nodes found", query=query)
            filtered = self._filter_where(all_nodes, where_clause, params)
            formatted = self._process_return([n.properties for n in filtered], return_part, filtered[0] if filtered else None)
            return GraphResult(columns=formatted["columns"], rows=formatted["rows"],
                              summary=f"Found {len(formatted['rows'])} result(s)", query=query)

        # Find connected pairs (or same node)
        rows: list[dict[str, Any]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for s in source_nodes:
            for t in target_nodes:
                key = (s.id, t.id)
                if key in seen_pairs:
                    continue
                rels = self._get_relationships(s.id, t.id, rel_type, direction)
                if rels or s.id == t.id:
                    seen_pairs.add(key)
                    # Aggregate count if needed
                    count = len(rels) if rels else 1
                    row: dict[str, Any] = {}
                    row[s_var or 'a'] = s.properties
                    row[t_var or 'b'] = t.properties
                    if "count" in return_part.lower() or "*" in return_part:
                        row["count"] = count
                    if rels and "r" in return_part.lower():
                        row["r"] = rels[0].properties
                    rows.append(row)

        if not rows:
            return GraphResult(columns=[], rows=[], summary="No connected pairs", query=query)

        # Apply WHERE filtering on rows
        if where_clause:
            rows = self._filter_where_rows(rows, where_clause, s_var, t_var, params)

        # Process RETURN clause to map var.property AS alias expressions
        formatted = self._process_return(rows, return_part)
        formatted["rows"] = self._apply_order_limit(return_part, formatted["rows"])
        cols = formatted["columns"] if formatted["columns"] else list(formatted["rows"][0].keys()) if formatted["rows"] else []
        return GraphResult(columns=cols, rows=formatted["rows"],
                          summary=f"Found {len(formatted['rows'])} result(s)", query=query)

    # ------------------------------------------------------------------ #
    # Pattern parsing helpers
    # ------------------------------------------------------------------ #

    def _parse_pattern(self, pattern_str: str) -> Optional[tuple]:
        """Parse ``(a:Label1 {props})-[:REL]->(b:Label2 {props})``."""
        # Strip variable-length path syntax
        pattern_str = re.sub(r'\*(\.\.\d+)?', '', pattern_str)

        # Find all node patterns: (var:Label {props}) or (var:Label) or (:Label)
        node_re = re.compile(r'\(\s*(\w*)\s*:?(\w*)\s*(?:\{([^}]*)\})?\s*\)')
        nodes = node_re.findall(pattern_str)
        if not nodes:
            return None

        # Find relationship type
        rel_match = re.search(r'\[:(\w+)\]', pattern_str)
        rel_type = rel_match.group(1) if rel_match else None

        # Determine direction
        if ']->' in pattern_str:
            direction = "out"
        elif ']<-' in pattern_str:
            direction = "in"
        else:
            direction = "both"

        if len(nodes) >= 2:
            s_var, s_label, s_props = nodes[0]
            t_var, t_label, t_props = nodes[1]
            s_p = self._parse_props(s_props, {}) if s_props else {}
            t_p = self._parse_props(t_props, {}) if t_props else {}
            return (s_label, s_var, s_p, rel_type, t_label, t_var, t_p, direction)
        elif len(nodes) == 1:
            s_var, s_label, s_props_str = nodes[0]
            props = self._parse_props(s_props_str, {}) if s_props_str else {}
            return (s_label, s_var, props, None, None, None, {}, "both")
        return None

    def _parse_props(self, props_str: str, params: dict) -> dict[str, Any]:
        """Parse a simple ``{key: value, key2: $param}`` property map."""
        props: dict[str, Any] = {}
        inner = props_str.strip()
        if not inner:
            return props
        for pair in inner.split(","):
            pair = pair.strip()
            if ":" not in pair:
                continue
            key, val = pair.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val.startswith("$"):
                if val[1:] in params:
                    props[key] = params[val[1:]]
            elif (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                props[key] = val[1:-1]
            else:
                try:
                    props[key] = int(val)
                except ValueError:
                    try:
                        props[key] = float(val)
                    except ValueError:
                        props[key] = val
        return props

    def _match_nodes(self, label: str, props: dict, params: dict) -> list[Node]:
        resolved: dict[str, Any] = {}
        for k, v in props.items():
            if isinstance(v, str) and v.startswith("$"):
                if v[1:] in params:
                    resolved[k] = params[v[1:]]
                else:
                    resolved[k] = v
            else:
                resolved[k] = v
        return self.find_nodes(label, resolved)

    def _get_relationships(self, source_id: str, target_id: str,
                           rel_type: Optional[str], direction: str) -> list[Relationship]:
        results: list[Relationship] = []
        if direction == "out":
            edges = self._graph.get_edge_data(source_id, target_id)
            if edges:
                for key, edata in edges.items():
                    if rel_type is None or edata.get("rel_type") == rel_type:
                        results.append(Relationship(
                            id=edata.get("props", {}).get("_rel_id", key),
                            type=edata.get("rel_type", ""),
                            source=source_id, target=target_id,
                            properties=dict(edata.get("props", {})),
                        ))
        elif direction == "in":
            edges = self._graph.get_edge_data(target_id, source_id)
            if edges:
                for key, edata in edges.items():
                    if rel_type is None or edata.get("rel_type") == rel_type:
                        results.append(Relationship(
                            id=edata.get("props", {}).get("_rel_id", key),
                            type=edata.get("rel_type", ""),
                            source=target_id, target=source_id,
                            properties=dict(edata.get("props", {})),
                        ))
        else:
            results.extend(self._get_relationships(source_id, target_id, rel_type, "out"))
            results.extend(self._get_relationships(source_id, target_id, rel_type, "in"))
        return results

    # ------------------------------------------------------------------ #
    # RETURN clause formatting helpers
    # ------------------------------------------------------------------ #

    def _process_return(self, rows: list[dict], return_clause: str, source_node=None) -> dict:
        """Map RETURN expressions like ``p.name AS person`` to actual values."""
        return_vars = return_clause.strip()
        return_vars = re.split(r"\s+ORDER\s+BY", return_vars, flags=re.IGNORECASE)[0]
        return_vars = re.split(r"\s+LIMIT", return_vars, flags=re.IGNORECASE)[0]
        if return_vars.upper().startswith("RETURN"):
            return_vars = return_vars[len("RETURN"):].strip()

        exprs = [e.strip() for e in return_vars.split(",")]
        columns = []
        for expr in exprs:
            if re.search(r"\s+AS\s+", expr, re.IGNORECASE):
                m = re.match(r"(.+?)\s+AS\s+(\w+)", expr, re.IGNORECASE)
                if m:
                    src_expr = m.group(1).strip()
                    alias = m.group(2).strip()
                    if src_expr.upper().startswith("COUNT"):
                        columns.append(("count", alias))
                    else:
                        columns.append((src_expr, alias))
                else:
                    columns.append((expr, expr))
            elif expr.upper().startswith("COUNT"):
                columns.append(("count", "count"))
            elif expr.startswith("labels("):
                columns.append(("labels", "labels"))
            elif re.match(r"\w+\.\w+", expr):
                m = re.match(r"(\w+)\.(\w+)", expr)
                if m:
                    columns.append((m.group(1) + "." + m.group(2), m.group(2)))
                else:
                    columns.append((expr, expr))
            else:
                columns.append((expr, expr))

        formatted_rows = []
        for row in rows:
            new_row = {}
            for src_expr, alias in columns:
                if src_expr == "count":
                    new_row[alias] = row.get("count", 1) if isinstance(row, dict) else 1
                elif src_expr == "labels" and source_node:
                    new_row[alias] = list(source_node.labels)
                elif "." in src_expr and not src_expr.startswith("count"):
                    # Expression is var.property
                    parts = src_expr.split(".", 1)
                    src_var = parts[0]
                    prop_name = parts[1]
                    src_data = row.get(src_var, {}) if isinstance(row, dict) else {}
                    if isinstance(src_data, dict):
                        new_row[alias] = src_data.get(prop_name)
                    else:
                        new_row[alias] = None
                elif isinstance(row, dict):
                    src_data = row.get(src_expr, row.get(alias, None))
                    if isinstance(src_data, dict):
                        new_row[alias] = src_data.get(alias, src_data)
                    else:
                        new_row[alias] = src_data
                else:
                    new_row[alias] = str(row) if row else row
            if not new_row and isinstance(row, dict):
                new_row = dict(row)
            formatted_rows.append(new_row)

        col_names = [c[1] for c in columns] if columns else (list(rows[0].keys()) if rows else [])
        return {"columns": col_names, "rows": formatted_rows}

    def _filter_where(self, nodes: list[Node], where_clause: str, params: dict) -> list[Node]:
        """Filter nodes based on a simple WHERE clause."""
        if not where_clause:
            return nodes
        result = []
        for n in nodes:
            if self._eval_where(where_clause, n.properties, params):
                result.append(n)
        return result

    def _filter_where_rows(self, rows: list[dict], where_clause: str, s_var: str, t_var: str, params: dict) -> list[dict]:
        """Filter result rows based on WHERE clause."""
        if not where_clause:
            return rows
        result = []
        for row in rows:
            props = {}
            for var in [s_var, t_var]:
                if var and var in row and isinstance(row[var], dict):
                    props.update(row[var])
            if self._eval_where(where_clause, props, params):
                result.append(row)
        return result

    def _eval_where(self, where_clause: str, props: dict, params: dict) -> bool:
        """Evaluate a simple WHERE clause against properties."""
        clause = where_clause
        # Handle toLower(var.prop) and contains()
        clause = re.sub(
            r"toLower\\s*\\(\\s*(\\w+)\\.(\\w+)\\s*\\)",
            lambda m: repr(str(props.get(m.group(2), "")).lower()), clause
        )
        # Handle CONTAINS
        clause = re.sub(
            r"\bCONTAINS\\s+", " in ", clause
        )
        # Handle remaining var.prop
        clause = re.sub(r"\b(\\w+)\\.(\\w+)\\b", lambda m: repr(props.get(m.group(2), "")), clause)
        # Handle params ($param)
        clause = re.sub(r"\$(\\w+)", lambda m: repr(params.get(m.group(1), "")), clause)
        try:
            return bool(eval(clause, {"__builtins__": {}}, {}))
        except Exception:
            return True

    def _apply_order_limit(self, return_clause: str, rows: list[dict]) -> list[dict]:
        order_match = re.search(r'ORDER\s+BY\s+(\w+)\s*(ASC|DESC)?', return_clause, re.IGNORECASE)
        if order_match and rows:
            col = order_match.group(1)
            reverse = (order_match.group(2) or "").upper() == "DESC"
            rows.sort(key=lambda r: r.get(col, 0), reverse=reverse)
        limit_match = re.search(r'LIMIT\s+(\d+)', return_clause, re.IGNORECASE)
        if limit_match:
            rows = rows[:int(limit_match.group(1))]
        skip_match = re.search(r'SKIP\s+(\d+)', return_clause, re.IGNORECASE)
        if skip_match:
            rows = rows[int(skip_match.group(1)):]
        return rows

    def _handle_shortest_path(self, match_body: str, return_clause: str, params: dict) -> GraphResult:
        sp_match = re.search(
            r'\(.*?:(\w+)\s*\{([^}]*)\}\s*\).*?\(.*?:(\w+)\s*\{([^}]*)\}\s*\)',
            match_body,
        )
        if not sp_match:
            return GraphResult(columns=[], rows=[], summary="Could not parse shortestPath", query="MATCH ... RETURN ...")

        source_label, sp_str, target_label, tp_str = sp_match.groups()
        source_props = self._parse_props(sp_str, params)
        target_props = self._parse_props(tp_str, params)
        path = self.shortest_path(source_label, source_props, target_label, target_props)

        if path is None:
            return GraphResult(columns=["path"], rows=[], summary="No path found", query="MATCH ... RETURN ...")

        return GraphResult(
            columns=["path"], rows=[{"path": path.to_dict()}],
            summary="Shortest path found", query="MATCH ... RETURN p",
        )

    # ------------------------------------------------------------------ #
    # Query handler: CREATE
    # ------------------------------------------------------------------ #
    def _handle_create(self, query: str, params: dict) -> GraphResult:
        node_matches = re.findall(r'\((\w*)\s*:\s*(\w+)\s*\{([^}]*)\}\)', query, re.IGNORECASE)
        node_ids: dict[str, str] = {}

        for var, label, props_str in node_matches:
            props = self._parse_props(props_str, params)
            nid = self.add_node(label, props)
            if var:
                node_ids[var] = nid

        if not node_matches:
            node_matches = re.findall(r'\((\w*)\s*:\s*(\w+)\)', query[6:].strip(), re.IGNORECASE)
            for var, label in node_matches:
                nid = self.add_node(label, {"name": var})
                if var:
                    node_ids[var] = nid

        rel_matches = re.findall(r'\((\w+)\)\s*-\s*\[:(\w+)\]\s*->\s*\(\s*(\w+)', query, re.IGNORECASE)
        for src, rtype, tgt in rel_matches:
            if src in node_ids and tgt in node_ids:
                self.add_relationship(node_ids[src], rtype, node_ids[tgt])

        return GraphResult(
            columns=["nodes_created", "relationships_created"],
            rows=[{"nodes_created": len(node_matches), "relationships_created": len(rel_matches)}],
            summary="Created nodes and relationships", query=query,
        )

    # ------------------------------------------------------------------ #
    # Query handler: MERGE
    # ------------------------------------------------------------------ #
    def _handle_merge(self, query: str, params: dict) -> GraphResult:
        node_pattern = re.findall(
            r'\(\s*(\w*)\s*:?(\w*)\s*(?:\{([^}]*)\})?\s*\)',
            query[6:].strip(),
            re.IGNORECASE,
        )
        node_ids: dict[str, str] = {}
        created = 0

        for var, label, props_str in node_pattern:
            props = self._parse_props(props_str, params) if props_str else {}
            existing = None
            if props:
                first_key = next(iter(props))
                existing = self.find_node(label, first_key, props[first_key])
            if existing:
                self.add_node(label, props, existing.id)
                node_ids[var] = existing.id
            else:
                nid = self.add_node(label, props)
                node_ids[var] = nid
                created += 1

        rel_matches = re.findall(r'\(\s*(\w+)\s*\)\s*-\s*\[:\s*(\w+)\s*\]\s*->\s*\(\s*(\w+)\s*\)', query, re.IGNORECASE)
        for src, rtype, tgt in rel_matches:
            if src in node_ids and tgt in node_ids:
                self.add_relationship(node_ids[src], rtype, node_ids[tgt])

        return GraphResult(
            columns=["nodes_merged", "nodes_created"],
            rows=[{"nodes_merged": len(node_pattern), "nodes_created": created}],
            summary="MERGE complete", query=query,
        )

    # ------------------------------------------------------------------ #
    # Query handler: SET (simplified)
    # ------------------------------------------------------------------ #
    def _handle_set(self, query: str, params: dict) -> GraphResult:
        return GraphResult(columns=[], rows=[], summary="SET acknowledged", query=query)

    # ------------------------------------------------------------------ #
    # Query handler: DELETE (simplified)
    # ------------------------------------------------------------------ #
    def _handle_delete(self, query: str, params: dict) -> GraphResult:
        node_var = re.search(r'DELETE\s+(\w+)', query, re.IGNORECASE)
        if node_var:
            var = node_var.group(1)
            nodes = self.find_nodes("", {var: True}) if var else []
            for n in nodes:
                self._graph.remove_node(n.id)
        return GraphResult(columns=[], rows=[], summary="DELETE acknowledged", query=query)

    # ------------------------------------------------------------------ #
    # Graph algorithms
    # ------------------------------------------------------------------ #
    def page_rank(self, top_n: int = 5) -> list[tuple[str, float]]:
        try:
            scores = nx.pagerank(self._graph)
        except Exception:
            return []
        sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result: list[tuple[str, float]] = []
        for nid, score in sorted_nodes[:top_n]:
            ndata = self._graph.nodes[nid]
            name = ndata["props"].get("name", ndata["props"].get("title", nid))
            result.append((name, round(score, 4)))
        return result

    def connected_components(self) -> list[list[str]]:
        undirected = self._graph.to_undirected()
        return [list(comp) for comp in nx.connected_components(undirected) if comp]

    def find_path(self, source_id: str, target_id: str, max_hops: int = 10) -> Optional[Path]:
        """Find any path between two node ids (not necessarily shortest)."""
        try:
            path_nodes = nx.shortest_path(self._graph, source=source_id, target=target_id)
        except nx.NetworkXNoPath:
            return None
        except nx.NodeNotFound:
            return None

        path = Path()
        for i, nid in enumerate(path_nodes):
            ndata = self._graph.nodes[nid]
            props = dict(ndata["props"])
            props["_id"] = nid
            node = Node(id=nid, labels=list(ndata["labels"]), properties=props)
            rel = None
            if i > 0:
                edge_data = self._graph.get_edge_data(path_nodes[i - 1], nid)
                if edge_data:
                    first_key = next(iter(edge_data))
                    edata = edge_data[first_key]
                    rel = Relationship(
                        id=edata.get("props", {}).get("_rel_id", f"rel_{i}"),
                        type=edata.get("rel_type", ""),
                        source=path_nodes[i - 1], target=nid,
                        properties=dict(edata.get("props", {})),
                    )
            path.steps.append(PathStep(node=node, relationship=rel))
        return path


