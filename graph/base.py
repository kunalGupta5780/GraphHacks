"""
Abstract graph context interface.

Every method below is implemented by both:
  * ``FalkorDBContext``  – real, persistent graph backed by FalkorDB
  * ``InMemoryContext``  – in-memory NetworkX graph for local dev / testing

The agent code talks only to this abstract interface, so it works
identically against the real database or the fallback.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Result containers
# --------------------------------------------------------------------------- #

@dataclass
class Node:
    """A node returned from a graph query."""
    id: str
    labels: list[str]
    properties: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        label_str = ":".join(self.labels)
        name = self.properties.get("name", self.properties.get("title", ""))
        return f"(:{label_str} {{name: {name!r}, id: {self.id}}})"


@dataclass
class Relationship:
    """A relationship returned from a graph query."""
    id: str
    type: str
    source: str       # node id
    target: str       # node id
    properties: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"-[:{self.type}]->"


@dataclass
class PathStep:
    """A single hop in a path – used for explainability."""
    node: Node
    relationship: Optional[Relationship] = None


@dataclass
class Path:
    """An ordered path of nodes and relationships."""
    steps: list[PathStep] = field(default_factory=list)

    @property
    def nodes(self) -> list[Node]:
        return [s.node for s in self.steps]

    @property
    def relationships(self) -> list[Relationship]:
        return [s.relationship for s in self.steps if s.relationship]

    def describe(self) -> str:
        parts = []
        for i, step in enumerate(self.steps):
            name = step.node.properties.get("name", step.node.properties.get("title", ""))
            labels = ":".join(step.node.labels)
            if i == 0:
                parts.append(f"(:{labels} {{name: {name}}})")
            else:
                if step.relationship:
                    parts.append(f"-[:{step.relationship.type}]->")
                parts.append(f"(:{labels} {{name: {name}}})")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [
                {
                    "node": {"id": s.node.id, "labels": s.node.labels, "properties": s.node.properties},
                    "relationship": (
                        {"id": s.relationship.id, "type": s.relationship.type,
                         "source": s.relationship.source, "target": s.relationship.target,
                         "properties": s.relationship.properties}
                        if s.relationship else None
                    ),
                }
                for s in self.steps
            ],
            "description": self.describe(),
        }


@dataclass
class GraphResult:
    """A generic result set from a graph query."""
    columns: list[str]
    rows: list[dict[str, Any]]
    summary: str = ""
    query: str = ""

    def __iter__(self):
        return iter(self.rows)

    def first(self) -> Optional[dict[str, Any]]:
        return self.rows[0] if self.rows else None

    def to_dicts(self) -> list[dict[str, Any]]:
        return self.rows

    def __len__(self) -> int:
        return len(self.rows)

    def __bool__(self) -> bool:
        return len(self.rows) > 0

    def describe(self) -> str:
        if not self.rows:
            return f"Query returned 0 rows. {self.summary}"
        lines = [f"Query returned {len(self.rows)} row(s). {self.summary}"]
        if self.columns:
            lines.append("  Columns: " + ", ".join(self.columns))
        for i, row in enumerate(self.rows[:5]):
            formatted = {k: str(v)[:80] for k, v in row.items()}
            lines.append(f"  Row {i}: {formatted}")
        if len(self.rows) > 5:
            lines.append(f"  ... and {len(self.rows) - 5} more row(s)")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Abstract interface
# --------------------------------------------------------------------------- #

class GraphContext(abc.ABC):
    """Abstract interface to a graph database context.

    All agent code depends on this interface, not on any specific
    backend.  Two implementations are shipped:
    ``FalkorDBContext`` (production) and ``InMemoryContext`` (dev/test).
    """

    @abc.abstractmethod
    def execute(self, query: str, params: Optional[dict] = None) -> GraphResult:
        """Run a Cypher-like query and return structured results."""
        ...

    @abc.abstractmethod
    def add_node(self, label: str, properties: dict[str, Any], node_id: Optional[str] = None) -> str:
        """Create or merge a node.  Returns the node's internal id."""
        ...

    @abc.abstractmethod
    def add_relationship(
        self,
        source_id: str,
        rel_type: str,
        target_id: str,
        properties: Optional[dict] = None,
    ) -> str:
        """Create a directed relationship between two nodes."""
        ...

    @abc.abstractmethod
    def find_node(self, label: str, property_name: str, property_value: Any) -> Optional[Node]:
        """Find a single node by label and property."""
        ...

    @abc.abstractmethod
    def find_nodes(self, label: str, properties: Optional[dict] = None) -> list[Node]:
        """Find all nodes with the given label and properties."""
        ...

    @abc.abstractmethod
    def shortest_path(
        self,
        source_label: str,
        source_props: dict[str, Any],
        target_label: str,
        target_props: dict[str, Any],
        max_hops: int = 10,
    ) -> Optional[Path]:
        """Find the shortest relationship path between two entities."""
        ...

    @abc.abstractmethod
    def neighbors(
        self,
        node_id: str,
        rel_types: Optional[list[str]] = None,
        direction: str = "both",
        max_depth: int = 1,
    ) -> list[Node]:
        """Get neighboring nodes of a given node."""
        ...

    @abc.abstractmethod
    def delete_graph(self) -> None:
        """Wipe everything (useful for testing / seed-load)."""
        ...

    @abc.abstractmethod
    def save_snapshot(self) -> dict[str, Any]:
        """Serialise graph metadata (node + edge counts, etc.)."""
        ...

    @abc.abstractmethod
    def get_graph_data(self) -> dict[str, Any]:
        """Return full graph data (nodes + edges) for visualisation."""
        ...

    @property
    @abc.abstractmethod
    def backend_name(self) -> str:
        """Human-readable name of the backend."""
        ...

    # Convenience helpers
    def explain_path(self, path: Optional[Path]) -> str:
        if not path or not path.steps:
            return "No path found."
        lines = ["**Reasoning path through the graph:**\n"]
        for i, step in enumerate(path.steps):
            name = step.node.properties.get("name", step.node.properties.get("title", ""))
            labels = ":".join(step.node.labels)
            if i == 0:
                lines.append(f"  1. Start at **{name}** (:{labels})")
            else:
                rel = step.relationship.type if step.relationship else "?"
                lines.append(f"  {i + 1}. Follow **{rel}** → **{name}** (:{labels})")
        return "\n".join(lines)