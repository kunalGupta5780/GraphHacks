"""
Configuration and context factory.

Tries to connect to a real FalkorDB instance first; if that fails,
falls back to the in-memory NetworkX backend so the agent works
everywhere – even without Docker.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .base import GraphContext

if TYPE_CHECKING:
    pass

# Environment variables with defaults
DB_HOST = os.getenv("FALKORDB_HOST", "localhost")
DB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
GRAPH_NAME = os.getenv("FALKORDB_GRAPH", "graphhacks")


def _try_falkordb() -> "GraphContext | None":
    """Attempt to create a live FalkorDB context; return None on failure."""
    try:
        from .falkordb_context import FalkorDBContext
        ctx = FalkorDBContext(host=DB_HOST, port=DB_PORT, graph_name=GRAPH_NAME)
        # Warm up
        ctx.execute("RETURN 1")
        return ctx
    except Exception:
        return None


def _try_inmemory() -> "GraphContext":
    from .inmemory_context import InMemoryContext
    return InMemoryContext()


def get_graph() -> "GraphContext":
    """Return the best available graph context.

    Preference order:
      1. FalkorDB (if a server is running)
      2. InMemoryContext (always available, works without Docker)
    """
    falkor = _try_falkordb()
    if falkor is not None:
        return falkor
    return _try_inmemory()
