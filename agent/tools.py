"""
High-level graph tools the agent can call.

Each method wraps a common query pattern and returns a structured
result.  These are the "tools" in the agent loop.
"""

from __future__ import annotations

from typing import Any, Optional

from graph.base import GraphContext, Node, Path
from graph.models import NodeType


class GraphTools:
    """Collection of ready-to-call graph query helpers."""

    def __init__(self, ctx: GraphContext) -> None:
        self._ctx = ctx

    @property
    def ctx(self) -> GraphContext:
        return self._ctx

    # ------------------------------------------------------------------ #
    # Knowledge tracing
    # ------------------------------------------------------------------ #

    def people_on_system(self, system_name: str) -> list[dict[str, Any]]:
        """Who has worked on projects that use *system_name*?"""
        query = (
            f"MATCH (p:Person)-[:WORKS_ON]->(:Project)-[:USES]->"
            f"(s:System {{name: '{system_name}'}})"
            f" RETURN p.name AS person, p.team AS team, p.role AS role"
        )
        result = self._ctx.execute(query)
        return result.to_dicts()

    def impact_analysis(self, system_name: str) -> list[dict[str, Any]]:
        """What depends on *system_name*?"""
        query = (
            f"MATCH (dep)-[:DEPENDS_ON]->(s:System {{name: '{system_name}'}})"
            f" RETURN dep.name AS dependent, labels(dep) AS types"
        )
        result = self._ctx.execute(query)
        return result.to_dicts()

    def who_knows(self, skill: str) -> list[dict[str, Any]]:
        """Who has *skill* in their profile?"""
        query = (
            f"MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)"
            f" WHERE toLower(s.name) CONTAINS toLower('{skill}')"
            f" RETURN p.name AS person, p.team AS team, p.role AS role"
        )
        result = self._ctx.execute(query)
        return result.to_dicts()

    def decision_trace(self, decision_title: str) -> dict[str, Any]:
        """Trace a decision to its source documents and meetings."""
        query = (
            f"MATCH (d:Decision {{title: '{decision_title}'}})"
            f"-[:BASED_ON]->(doc:Document) RETURN doc"
        )
        docs = self._ctx.execute(query)
        query2 = (
            f"MATCH (d:Decision {{title: '{decision_title}'}})"
            f"-[:MADE_IN]->(m:Meeting) RETURN m"
        )
        mtgs = self._ctx.execute(query2)
        return {"documents": docs.to_dicts(), "meetings": mtgs.to_dicts()}

    def ownership_chain(self, system_name: str) -> Optional[dict[str, Any]]:
        """Who owns a system?"""
        query = (
            f"MATCH (owner:Person)-[:OWNS]->(s:System {{name: '{system_name}'}})"
            f" RETURN owner.name AS owner, owner.role AS role, owner.team AS team"
        )
        result = self._ctx.execute(query)
        return result.first()

    def system_dependencies(self, system_name: str) -> list[dict[str, Any]]:
        """What does this system depend on?"""
        query = (
            f"MATCH (s:System {{name: '{system_name}'}})-[:DEPENDS_ON]->(dep)"
            f" RETURN dep.name AS dependency, labels(dep) AS types"
        )
        result = self._ctx.execute(query)
        return result.to_dicts()

    def find_connection(self, source: str, target: str) -> Optional[dict[str, Any]]:
        """Find the shortest path between two named entities."""
        for src_label, tgt_label in [("Person", "System"), ("System", "System"),
                                      ("Project", "System"), ("Person", "Project")]:
            path = self._ctx.shortest_path(src_label, {"name": source},
                                           tgt_label, {"name": target})
            if path:
                return path.to_dict()
        return None

    # ------------------------------------------------------------------ #
    # Graph algorithms
    # ------------------------------------------------------------------ #

    def page_rank(self, top_n: int = 5) -> list[tuple[str, float]]:
        """Return the top-N most important nodes by PageRank."""
        if hasattr(self._ctx, "page_rank"):
            return self._ctx.page_rank(top_n)  # type: ignore
        return []

    def central_persons(self, top_n: int = 5) -> list[dict[str, Any]]:
        """Find the most central people in the collaboration graph."""
        pr = self.page_rank(top_n * 3)
        persons = []
        for name, score in pr:
            node = self._ctx.find_node("Person", "name", name)
            if node:
                persons.append({"name": name, "score": score})
        return persons[:top_n]

    # ------------------------------------------------------------------ #
    # Actions – write back to the graph
    # ------------------------------------------------------------------ #

    def add_concept(self, name: str, description: str, source: str = "") -> str:
        """Add a learned concept to the graph."""
        nid = self._ctx.add_node(NodeType.CONCEPT.value, {
            "name": name, "description": description,
            "source": source, "confidence": 1.0,
        })
        return nid

    def link_concept_to_session(self, concept_id: str, session_id: str) -> None:
        """Link a concept to a session memory node."""
        session = self._ctx.find_node(NodeType.MEMORY.value, "name", session_id)
        if session:
            from ..graph.models import RelationshipType
            self._ctx.add_relationship(
                concept_id, RelationshipType.RECALLS.value, session.id
            )