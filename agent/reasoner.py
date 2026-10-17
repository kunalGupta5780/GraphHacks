"""
Multi-hop reasoning engine.

The ``GraphReasoner`` is the core of the agent.  It takes a user
question, decides which graph traversal to attempt, executes it
through the ``GraphContext`` interface, and returns both the answer
and a structured explanation of *how* the graph was followed.

Key design principle: **the graph shapes what the agent does**, not
the other way around.  Every decision, every fact, every answer
must be traceable to a path in the graph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from graph.base import GraphContext, Node, Relationship, Path, PathStep, GraphResult


@dataclass
class ReasoningStep:
    """A single step in the agent's reasoning chain."""
    action: str          # e.g. "find_node", "traverse", "shortest_path"
    description: str      # human-readable description
    query: str           # the Cypher / internal query used
    result_summary: str  # what was found
    evidence: list[dict] = field(default_factory=list)


@dataclass
class Answer:
    """Structured answer returned by the reasoner."""
    question: str
    answer: str
    confidence: float = 1.0
    confidence_reason: str = ""
    steps: list[ReasoningStep] = field(default_factory=list)
    paths: list[dict] = field(default_factory=list)  # serialized Path objects
    raw_results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "confidence": self.confidence,
            "confidence_reason": self.confidence_reason,
            "steps": [s.__dict__ for s in self.steps],
            "paths": self.paths,
            "raw_results": self.raw_results,
        }


class GraphReasoner:
    """Orchestrates multi-hop graph traversals to answer questions."""

    def __init__(self, ctx: GraphContext) -> None:
        self._ctx = ctx

    @property
    def ctx(self) -> GraphContext:
        return self._ctx

    def ask(self, question: str, params: Optional[dict] = None) -> Answer:
        """Answer a user question by traversing the graph."""
        params = params or {}
        q = question.lower()

        if "who" in q and ("system" in q or "work" in q):
            return self._ask_who_knows_about_system(question, params)
        if "break" in q or "down" in q or "impact" in q:
            return self._ask_impact_analysis(question, params)
        if "decision" in q or "why" in q or "rationale" in q:
            return self._ask_decision_trace(question, params)
        if "ask" in q or "request" in q or "last" in q:
            return self._ask_conversation_trace(question, params)
        if "who" in q and ("know" in q or "skill" in q):
            return self._ask_who_knows(question, params)
        if "path" in q or "how" in q or "connect" in q:
            return self._ask_path(question, params)
        return self._ask_general(question, params)

    # ------------------------------------------------------------------ #
    # Specialized handlers
    # ------------------------------------------------------------------ #

    def _ask_who_knows_about_system(self, question: str, params: dict) -> Answer:
        """Who on the team has worked on this system?

        Traverses: Person -> works_on -> Project -> uses -> System
        """
        steps: list[ReasoningStep] = []
        system_name = params.get("system") or self._extract_name(question, ["system", "system\""])
        if not system_name:
            system_name = self._extract_entity(question)

        # Step 1: Find the system node
        sys_node = self._ctx.find_node("System", "name", system_name)
        query1 = f"MATCH (s:System {{name: '{system_name}'}}) RETURN s"
        if not sys_node:
            steps.append(ReasoningStep(
                "find_node", f"Locating system '{system_name}'", query1,
                f"Found 0 systems named '{system_name}'", []
            ))
            return Answer(
                question=question,
                answer=f"No system named '{system_name}' was found in the knowledge graph.",
                confidence=0.0, confidence_reason="System not found in graph",
                steps=steps,
            )

        steps.append(ReasoningStep(
            "find_node", f"Found system '{system_name}'", query1,
            f"Node id={sys_node.id}, criticality={sys_node.properties.get('criticality')}", [sys_node.properties]
        ))

        # Step 2: Traverse Person -> Project -> System
        query2 = (
            f"MATCH (p:Person)-[:WORKS_ON]->(:Project)-[:USES]->(s:System {{name: '{system_name}'}})"
            f" RETURN p.name AS person, count(*) AS projects ORDER BY projects DESC"
        )
        result = self._ctx.execute(query2)
        steps.append(ReasoningStep(
            "traverse", f"Following WORKS_ON -> USES path from {system_name}", query2,
            f"Found {len(result.rows)} person(s)", result.to_dicts()
        ))

        people = result.to_dicts()
        if not people:
            answer = f"No one has worked on {system_name} according to the graph."
            confidence = 0.5
            conf_reason = "No WORKS_ON relationships found for this system"
        else:
            names = [r["person"] for r in people]
            counts = [f"{r['person']} ({r['projects']} project{'s' if r['projects'] > 1 else ''})" for r in people]
            answer = f"People who have worked on **{system_name}**:\n" + \
                     "\n".join(f"  - {c}" for c in counts)
            confidence = 0.95
            conf_reason = "Path traced: Person -> WORKS_ON -> Project -> USES -> System"

        # Build explanation path
        paths = []
        for p in people:
            person_node = self._ctx.find_node("Person", "name", p["person"])
            if person_node and sys_node:
                path = self._ctx.shortest_path("Person", {"name": p["person"]},
                                               "System", {"name": system_name})
                if path:
                    paths.append(path.to_dict())

        return Answer(
            question=question, answer=answer,
            confidence=confidence, confidence_reason=conf_reason,
            steps=steps, paths=paths,
            raw_results=people,
        )

    def _ask_impact_analysis(self, question: str, params: dict) -> Answer:
        """What breaks if this service goes down?

        Traverses: System -> depends_on (reverse) -> System/Project
        """
        steps: list[ReasoningStep] = []
        system_name = params.get("system") or self._extract_entity(question)

        sys_node = self._ctx.find_node("System", "name", system_name)
        query1 = f"MATCH (s:System {{name: '{system_name}'}}) RETURN s"
        if not sys_node:
            steps.append(ReasoningStep(
                "find_node", f"Locating system '{system_name}'", query1,
                "System not found", []
            ))
            return Answer(
                question=question,
                answer=f"No system named '{system_name}' was found.",
                confidence=0.0, confidence_reason="System not found",
                steps=steps,
            )

        steps.append(ReasoningStep(
            "find_node", f"Found system '{system_name}'", query1,
            f"id={sys_node.id}, criticality={sys_node.properties.get('criticality')}", [sys_node.properties]
        ))

        # Find things that DEPENDS_ON this system
        query2 = (
            f"MATCH (dep)-[:DEPENDS_ON]->(s:System {{name: '{system_name}'}})"
            f" RETURN dep.name AS dependent, labels(dep) AS dep_type, "
            f"collect(DISTINCT head(labels(dep))) AS types"
        )
        result = self._ctx.execute(query2)
        steps.append(ReasoningStep(
            "traverse", f"Finding everything that depends on {system_name}", query2,
            f"Found {len(result.rows)} dependent entity/ies", result.to_dicts()
        ))

        dependents = result.to_dicts()
        if not dependents:
            answer = f"Nothing in the graph depends on **{system_name}**, so a failure would have no downstream impact according to current data."
            confidence = 0.3
            conf_reason = "No DEPENDS_ON relationships found"
        else:
            lines = [f"If **{system_name}** goes down, these systems/projects are affected:"]
            for d in dependents:
                name = d.get("dependent", "")
                types = ", ".join(d.get("types", [])) if isinstance(d.get("types"), list) else str(d.get("types", ""))
                lines.append(f"  - {name} ({types})")

                # Find the shortest path for explainability
                dep_node = self._ctx.find_node("System", "name", name)
                if dep_node:
                    path = self._ctx.shortest_path(
                        "System", {"name": name},
                        "System", {"name": system_name}
                    )
                    if path:
                        steps.append(ReasoningStep(
                            "shortest_path", f"Path: {name} -> {system_name}",
                            f"MATCH p=shortestPath((:System {{name: '{name}'}})-[:DEPENDS_ON]->(:System {{name: '{system_name}'}})) RETURN p",
                            path.describe(), path.to_dict()
                        ))

            answer = "\n".join(lines)
            confidence = 0.9
            conf_reason = "Reverse-dependency traversal via DEPENDS_ON edges"

        return Answer(
            question=question, answer=answer,
            confidence=confidence, confidence_reason=conf_reason,
            steps=steps, raw_results=dependents,
        )

    def _ask_decision_trace(self, question: str, params: dict) -> Answer:
        """Trace a decision back to its source.

        Traverses: Decision -> based_on -> Document, Decision -> made_in -> Meeting
        """
        steps = []
        topic = params.get("decision") or self._extract_entity(question)

        dec_node = self._ctx.find_node("Decision", "title", topic)
        query1 = f"MATCH (d:Decision {{title: '{topic}'}}) RETURN d"
        if not dec_node:
            steps.append(ReasoningStep(
                "find_node", f"Locating decision '{topic}'", query1, "Not found", []
            ))
            return Answer(
                question=question,
                answer=f"No decision about '{topic}' was found in the graph.",
                confidence=0.0, confidence_reason="Decision not found", steps=steps,
            )

        steps.append(ReasoningStep(
            "find_node", f"Found decision: {dec_node.properties.get('title')}", query1,
            f"status={dec_node.properties.get('status')}", [dec_node.properties]
        ))

        # Follow BASED_ON -> Document
        query2 = f"MATCH (d:Decision {{title: '{topic}'}})-[:BASED_ON]->(doc:Document) RETURN doc"
        docs_result = self._ctx.execute(query2)
        docs = docs_result.to_dicts()
        steps.append(ReasoningStep(
            "traverse", "Tracing BASED_ON documents", query2,
            f"Found {len(docs)} document(s)", docs
        ))

        # Follow MADE_IN -> Meeting
        query3 = f"MATCH (d:Decision {{title: '{topic}'}})-[:MADE_IN]->(m:Meeting) RETURN m"
        mtgs_result = self._ctx.execute(query3)
        mtgs = mtgs_result.to_dicts()
        steps.append(ReasoningStep(
            "traverse", "Tracing MADE_IN meetings", query3,
            f"Found {len(mtgs)} meeting(s)", mtgs
        ))

        answer_parts = [f"**Decision: {dec_node.properties.get('title')}**"]
        rationale = dec_node.properties.get("rationale", "")
        if rationale:
            answer_parts.append(f"  Rationale: {rationale}")
        outcome = dec_node.properties.get("outcome", "")
        if outcome:
            answer_parts.append(f"  Outcome: {outcome}")
        date = dec_node.properties.get("date", "")
        if date:
            answer_parts.append(f"  Date: {date}")

        if docs:
            answer_parts.append("  **Source documents:**")
            for d in docs:
                answer_parts.append(f"    - {d.get('title', '')} ({d.get('type', '')})")

        if mtgs:
            answer_parts.append("  **Decided in meetings:**")
            for m in mtgs:
                answer_parts.append(f"    - {m.get('title', '')} ({m.get('date', '')})")

        # Build a path for explainability
        paths = []
        if docs:
            doc_title = docs[0].get("title", "")
            path = self._ctx.shortest_path("Decision", {"title": topic},
                                           "Document", {"title": doc_title})
            if path:
                paths.append(path.to_dict())

        answer = "\n".join(answer_parts)
        return Answer(
            question=question, answer=answer,
            confidence=0.9, confidence_reason="Decision traced to source documents and meetings",
            steps=steps, paths=paths,
            raw_results=docs + mtgs,
        )

    def _ask_conversation_trace(self, question: str, params: dict) -> Answer:
        """What did a person ask for recently? Was it resolved?"""
        steps = []
        person_name = params.get("person") or self._extract_entity(question, ["asked", "customer", "request"])

        # Find conversation messages from this person
        query1 = (
            f"MATCH (root:Memory)-[:IN_CONTEXT]->(c) "
            f"WHERE c.speaker = '{person_name}' "
            f"RETURN c.content AS content, c.timestamp AS ts "
            f"ORDER BY c.timestamp DESC LIMIT 10"
        )
        result = self._ctx.execute(query1)
        steps.append(ReasoningStep(
            "traverse", f"Searching conversation history for '{person_name}'", query1,
            f"Found {len(result.rows)} conversation(s)", result.to_dicts()
        ))

        hist = result.to_dicts()
        if not hist:
            answer = f"No conversation history found for '{person_name}' in the graph."
            confidence = 0.2
            conf_reason = "No IN_CONTEXT edges found for this speaker"
        else:
            latest = hist[0]
            answer = f"**Last message from {person_name}:**\n  {latest.get('content', '')[:200]}"
            answer += f"\n\n**Was it resolved?**"
            # Check if there are related tickets or decisions
            tkt_query = (
                f"MATCH (t:Ticket) WHERE t.assignee = '{person_name}' "
                f"RETURN t.title AS title, t.status AS status"
            )
            tkt_result = self._ctx.execute(tkt_query)
            tickets = tkt_result.to_dicts()
            if tickets:
                answer += "\n  Related tickets:\n"
                for t in tickets:
                    answer += f"  - {t['title']} ({t['status']})"
            else:
                answer += "\n  No related tickets found."

            confidence = 0.8
            conf_reason = "Found conversation history and checked ticket resolution status"

        return Answer(
            question=question, answer=answer,
            confidence=confidence, confidence_reason=conf_reason,
            steps=steps, raw_results=hist,
        )

    def _ask_who_knows(self, question: str, params: dict) -> Answer:
        """Who on the team has a skill / knows about something?"""
        steps = []
        keyword = params.get("skill") or self._extract_entity(question)

        query1 = (
            f"MATCH (p:Person)-[:HAS_SKILL]->(s:Skill) "
            f"WHERE toLower(s.name) CONTAINS toLower('{keyword}') "
            f"RETURN p.name AS name, p.team AS team, p.role AS role "
            f"ORDER BY p.name"
        )
        result = self._ctx.execute(query1)
        steps.append(ReasoningStep(
            "traverse", f"Searching for people with skill '{keyword}'", query1,
            f"Found {len(result.rows)} person(s)", result.to_dicts()
        ))

        people = result.to_dicts()
        if not people:
            answer = f"No one in the knowledge graph is tagged with skills related to '{keyword}'."
            confidence = 0.3
            conf_reason = "No HAS_SKILL relationships matched"
        else:
            lines = [f"People who know about **{keyword}**:"]
            for p in people:
                lines.append(f"  - {p['name']} ({p.get('role', '')} on {p.get('team', '')})")
            answer = "\n".join(lines)
            confidence = 0.9
            conf_reason = "HAS_SKILL edges found in graph"

        return Answer(
            question=question, answer=answer,
            confidence=confidence, confidence_reason=conf_reason,
            steps=steps, raw_results=people,
        )

    def _ask_path(self, question: str, params: dict) -> Answer:
        """Show how two entities are connected."""
        steps = []
        source_name = params.get("source") or "FalkorDB"
        target_name = params.get("target") or self._extract_entity(question)

        src_node = self._ctx.find_node("System", "name", source_name)
        tgt_node = self._ctx.find_node("Person", "name", target_name) or \
                   self._ctx.find_node("Project", "name", target_name)

        query = f"MATCH p=shortestPath((:System {{name: '{source_name}'}})-[*..10]-(n)) WHERE n.name = '{target_name}' RETURN p"
        path = None
        if src_node and tgt_node:
            path = self._ctx.shortest_path("System", {"name": source_name},
                                           tgt_node.labels[0], {"name": target_name})
        if not path and src_node and tgt_node:
            path = self._ctx.find_path(src_node.id, tgt_node.id)

        steps.append(ReasoningStep(
            "shortest_path", f"Finding connection: {source_name} -> {target_name}",
            query, path.describe() if path else "No path found",
            [path.to_dict()] if path else []
        ))

        if path:
            answer = self._ctx.explain_path(path)
            confidence = 0.95
            conf_reason = "Shortest path found between entities"
            paths = [path.to_dict()]
        else:
            answer = f"No connection found between '{source_name}' and '{target_name}' in the graph."
            confidence = 0.3
            conf_reason = "No path exists between the two entities"
            paths = []

        return Answer(
            question=question, answer=answer,
            confidence=confidence, confidence_reason=conf_reason,
            steps=steps, paths=paths,
        )

    def _ask_general(self, question: str, params: dict) -> Answer:
        """Fallback: search for any node matching the question text."""
        steps = []
        keyword = self._extract_entity(question)

        query = (
            f"MATCH (n) WHERE toLower(n.name) CONTAINS toLower('{keyword}') "
            f"OR toLower(n.title) CONTAINS toLower('{keyword}') "
            f"RETURN n.name AS name, labels(n) AS labels"
        )
        result = self._ctx.execute(query)
        steps.append(ReasoningStep(
            "search", f"Searching graph for '{keyword}'", query,
            f"Found {len(result.rows)} match(es)", result.to_dicts()
        ))

        matches = result.to_dicts()
        if not matches:
            answer = f"I searched the knowledge graph for '{keyword}' but found no matching entities."
            confidence = 0.2
            conf_reason = "Keyword search returned no results"
        else:
            lines = [f"Found {len(matches)} relevant entity(ies) for '{keyword}':"]
            for m in matches:
                labels = ", ".join(m.get("labels", [])) if isinstance(m.get("labels"), list) else str(m.get("labels", ""))
                lines.append(f"  - {m.get('name', '')} ({labels})")

                # Try to build a path to this node from something well-known
                name = m.get("name", "")
                falkordb_node = self._ctx.find_node("System", "name", "FalkorDB")
                target_node = self._ctx.find_node(m.get("labels", [""])[0], "name", name) if m.get("labels") else None
                if falkordb_node and target_node:
                    path = self._ctx.shortest_path(
                        "System", {"name": "FalkorDB"},
                        target_node.labels[0], {"name": name}
                    )
                    if path:
                        steps.append(ReasoningStep(
                            "shortest_path",
                            f"Connection from FalkorDB to {name}",
                            "shortestPath(...)", path.describe(), [path.to_dict()]
                        ))
                        lines.append(f"    Path: {path.describe()}")

            answer = "\n".join(lines)
            confidence = 0.7
            conf_reason = "Keyword search in graph"

        return Answer(
            question=question, answer=answer,
            confidence=confidence, confidence_reason=conf_reason,
            steps=steps, raw_results=matches,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _extract_entity(self, question: str, stopwords: Optional[list[str]] = None) -> str:
        """Extract a likely entity name from the question text."""
        stopwords = stopwords or []
        # Remove question words and common verbs
        cleaned = re.sub(r'\b(who|what|which|where|when|why|how|is|are|the|a|an|to|on|in|at|for|of|and|or)\b',
                         '', question, flags=re.IGNORECASE)
        for sw in stopwords:
            cleaned = re.sub(r'\b' + re.escape(sw) + r'\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'[^\w\s]', '', cleaned).strip()
        # Take the longest word as the entity name
        words = cleaned.split()
        if words:
            return max(words, key=len)
        return cleaned

    def _extract_name(self, question: str, keywords: list[str]) -> Optional[str]:
        """Try to extract a name following a keyword in the question."""
        for kw in keywords:
            pattern = re.escape(kw) + r'\s+(?:is|the|for|on|about|who|work|break|down)?\s*([A-Z][\w\s]+)'
            m = re.search(pattern, question, re.IGNORECASE)
            if m:
                return m.group(1).strip().rstrip('?')
        return None
