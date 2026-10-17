"""
Graph context layer for GraphHacks agent.
Provides both real FalkorDB integration and an in-memory fallback.
"""

from .base import GraphContext, GraphResult, Node, Relationship, Path, PathStep
from .models import (
    NodeType, RelationshipType,
    Person, Project, System, Document, Decision,
    Meeting, Ticket, Skill, Team, Concept, Conversation, Memory,
)
from .config import get_graph

__all__ = [
    "GraphContext", "GraphResult", "Node", "Relationship", "Path", "PathStep",
    "NodeType", "RelationshipType",
    "Person", "Project", "System", "Document", "Decision",
    "Meeting", "Ticket", "Skill", "Team", "Concept", "Conversation", "Memory",
    "get_graph",
]

