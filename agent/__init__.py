"""
Agent layer for GraphHacks.

Components:
  * ``AgentMemory``   – persistent episodic / semantic / procedural memory
  * ``GraphReasoner`` – multi-hop reasoning over the graph
  * ``GraphExplainer``– explainability: turns paths into natural-language traces
  * ``GraphTools``    – high-level helper functions the agent calls
"""

from .memory import AgentMemory
from .reasoner import GraphReasoner
from .explainer import GraphExplainer
from .tools import GraphTools

__all__ = ["AgentMemory", "GraphReasoner", "GraphExplainer", "GraphTools"]
