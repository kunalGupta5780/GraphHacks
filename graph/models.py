"""
Data models for graph entities.

Each model maps to a node in the graph and knows how to serialize
itself into the (label, properties) tuple that the context layer
expects.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class NodeType(str, Enum):
    PERSON = "Person"
    PROJECT = "Project"
    SYSTEM = "System"
    DOCUMENT = "Document"
    DECISION = "Decision"
    MEETING = "Meeting"
    TICKET = "Ticket"
    SKILL = "Skill"
    TEAM = "Team"
    CONCEPT = "Concept"
    CONVERSATION = "Conversation"
    MEMORY = "Memory"


class RelationshipType(str, Enum):
    # People
    WORKS_ON = "WORKS_ON"
    MEMBER_OF = "MEMBER_OF"
    HAS_SKILL = "HAS_SKILL"
    KNOWN_FOR = "KNOWN_FOR"
    RAISED = "RAISED"
    RESOLVED = "RESOLVED"
    OWNS = "OWNS"
    ATTENDED = "ATTENDED"
    ASKED = "ASKED"
    LEARNED = "LEARNED"

    # Projects / Systems / Documents
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    HAS_DOCUMENT = "HAS_DOCUMENT"
    HAS_DECISION = "HAS_DECISION"
    HAS_TICKET = "HAS_TICKET"
    HAS_MEETING = "HAS_MEETING"
    BASED_ON = "BASED_ON"
    MADE_IN = "MADE_IN"
    TRACKS = "TRACKS"
    RELATED_TO = "RELATED_TO"
    REFERENCES = "REFERENCES"
    APPROVED_BY = "APPROVED_BY"
    IMPACTS = "IMPACTS"

    # Memory
    REMEMBERED_IN = "REMEMBERED_IN"
    RECALLS = "RECALLS"
    IN_CONTEXT = "IN_CONTEXT"


# --------------------------------------------------------------------------- #
# Dataclasses for each entity type
# --------------------------------------------------------------------------- #

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class Person:
    name: str
    role: str = ""
    team: str = ""
    email: str = ""
    skills: list[str] = field(default_factory=list)
    hire_date: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props.pop("skills", None)
        props["type"] = "person"
        return (NodeType.PERSON.value, props)


@dataclass
class Project:
    name: str
    description: str = ""
    status: str = "active"
    start_date: str = ""
    end_date: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "project"
        return (NodeType.PROJECT.value, props)


@dataclass
class System:
    name: str
    type: str = "service"
    criticality: str = "medium"
    owner: str = ""
    description: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "system"
        return (NodeType.SYSTEM.value, props)


@dataclass
class Document:
    title: str
    type: str = "doc"
    summary: str = ""
    created_by: str = ""
    created_date: str = ""
    url: str = ""
    content: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "document"
        return (NodeType.DOCUMENT.value, props)


@dataclass
class Decision:
    title: str
    rationale: str = ""
    date: str = ""
    status: str = "accepted"
    outcome: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "decision"
        return (NodeType.DECISION.value, props)


@dataclass
class Meeting:
    title: str
    date: str = ""
    agenda: str = ""
    notes: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "meeting"
        return (NodeType.MEETING.value, props)


@dataclass
class Ticket:
    title: str
    description: str = ""
    status: str = "open"
    priority: str = "medium"
    assignee: str = ""
    created_date: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "ticket"
        return (NodeType.TICKET.value, props)


@dataclass
class Skill:
    name: str
    category: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "skill"
        return (NodeType.SKILL.value, props)


@dataclass
class Team:
    name: str
    description: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "team"
        return (NodeType.TEAM.value, props)


@dataclass
class Concept:
    name: str
    description: str = ""
    confidence: float = 1.0
    source: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "concept"
        return (NodeType.CONCEPT.value, props)


@dataclass
class Conversation:
    content: str
    speaker: str = ""
    timestamp: str = ""
    session_id: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "conversation"
        return (NodeType.CONVERSATION.value, props)


@dataclass
class Memory:
    content: str
    category: str = "episodic"
    timestamp: str = ""
    session_id: str = ""
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source_query: str = ""
    node_id: Optional[str] = None

    def to_node(self):
        props = asdict(self)
        props.pop("node_id", None)
        props["type"] = "memory"
        return (NodeType.MEMORY.value, props)
