"""
Agent memory system.

Implements three types of memory, all persisted in the graph:

* **Episodic** – conversation turns (user <-> agent) tied to a session.
* **Semantic** – facts and concepts the agent has learned.
* **Procedural** – how-to patterns the agent recorded for future use.

Memory lives in the graph so every agent instance (or every session)
can read and write it.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from graph.base import GraphContext
from graph.models import (
    NodeType, RelationshipType,
    Conversation as ConvModel, Concept,
)


class AgentMemory:
    """Persistent memory backed by the graph context."""

    def __init__(self, ctx: GraphContext, user_id: str = "default") -> None:
        self._ctx = ctx
        self._user_id = user_id
        self.session_id = str(uuid.uuid4())[:8]

        # Ensure a session root node exists
        session_node = ctx.find_node(NodeType.MEMORY.value, "name", self._user_id)
        if not session_node:
            nid = ctx.add_node(
                NodeType.MEMORY.value,
                {
                    "name": self._user_id,
                    "type": "session_root",
                    "session_id": self._user_id,
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
            self._session_root_id = nid
        else:
            self._session_root_id = session_node.id

    # ---------------------------------------------------------------
    # Episodic memory - conversation turns
    # ---------------------------------------------------------------

    def log_conversation(self, speaker: str, content: str) -> None:
        """Store a conversation turn in the graph."""
        conv = ConvModel(
            content=content,
            speaker=speaker,
            timestamp=datetime.utcnow().isoformat(),
            session_id=self._user_id,
        )
        label, props = conv.to_node()
        nid = self._ctx.add_node(label, props)
        self._ctx.add_relationship(
            self._session_root_id, RelationshipType.IN_CONTEXT.value, nid
        )

    def recall_conversation(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve the last *limit* conversation turns."""
        q = (
            f"MATCH (root:Memory {{name: $uid}})-[:{RelationshipType.IN_CONTEXT.value}]->(c)"
            f" RETURN c.content AS content, c.speaker AS speaker, c.timestamp AS ts "
            f"ORDER BY c.timestamp ASC LIMIT {limit}"
        )
        result = self._ctx.execute(q, {"uid": self._user_id})
        return result.to_dicts() if result.rows else []

    # ---------------------------------------------------------------
    # Semantic memory - learned facts / concepts
    # ---------------------------------------------------------------

    def remember_fact(self, concept_name: str, description: str,
                      confidence: float = 1.0, source: str = "",
                      tags: Optional[list[str]] = None) -> None:
        """Store or update a semantic fact in the graph."""
        tags = tags or []
        existing = self._ctx.find_node(NodeType.CONCEPT.value, "name", concept_name)
        props = {
            "name": concept_name,
            "description": description,
            "confidence": confidence,
            "source": source,
            "tags": json.dumps(tags),
            "timestamp": datetime.utcnow().isoformat(),
        }
        if existing:
            self._ctx.add_node(NodeType.CONCEPT.value, props, existing.id)
        else:
            nid = self._ctx.add_node(NodeType.CONCEPT.value, props)
            self._ctx.add_relationship(
                nid, RelationshipType.LEARNED.value, self._session_root_id
            )

    def recall_fact(self, concept_name: str) -> Optional[dict[str, Any]]:
        """Look up a concept by name."""
        node = self._ctx.find_node(NodeType.CONCEPT.value, "name", concept_name)
        return node.properties if node else None

    def search_facts(self, keyword: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search concepts containing *keyword*."""
        all_concepts = self._ctx.find_nodes(NodeType.CONCEPT.value)
        results = []
        for c in all_concepts:
            desc = c.properties.get("description", "").lower()
            name = c.properties.get("name", "").lower()
            if keyword.lower() in desc or keyword.lower() in name:
                results.append(c.properties)
        return results[:limit]

    # ---------------------------------------------------------------
    # Procedural memory - how-to patterns
    # ---------------------------------------------------------------

    def record_procedure(self, action: str, steps: list[str], success: bool = True) -> None:
        """Record a procedure for future recall."""
        proc_id = f"proc_{action.replace(' ', '_').lower()}"
        props = {
            "name": action,
            "steps": json.dumps(steps),
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        }
        nid = self._ctx.add_node(NodeType.CONCEPT.value, props, node_id=proc_id)
        if not self._ctx.find_node(NodeType.CONCEPT.value, "name", action):
            self._ctx.add_relationship(
                nid, RelationshipType.LEARNED.value, self._session_root_id
            )

    def recall_procedure(self, action: str) -> Optional[list[str]]:
        """Retrieve steps for a recorded procedure."""
        proc_id = f"proc_{action.replace(' ', '_').lower()}"
        node = self._ctx.find_node(NodeType.CONCEPT.value, "_id", proc_id)
        if not node:
            node = self._ctx.find_node(NodeType.CONCEPT.value, "name", action)
        if not node:
            return None
        steps_str = node.properties.get("steps", "[]")
        try:
            return json.loads(steps_str)
        except (json.JSONDecodeError, TypeError):
            return []

    # ---------------------------------------------------------------
    # Context assembly for prompts
    # ---------------------------------------------------------------

    def get_context(self, max_turns: int = 5, max_facts: int = 10) -> dict[str, Any]:
        """Assemble a context packet for the agent's system prompt."""
        history = self.recall_conversation(limit=max_turns)
        facts_result = self._ctx.find_nodes(NodeType.CONCEPT.value)
        facts = []
        for c in facts_result[:max_facts]:
            facts.append({
                "name": c.properties.get("name", ""),
                "description": c.properties.get("description", ""),
                "confidence": c.properties.get("confidence", 1.0),
            })
        return {
            "session_id": self.session_id,
            "user_id": self._user_id,
            "backend": self._ctx.save_snapshot().get("backend", "unknown"),
            "history": history,
            "facts": facts,
        }
