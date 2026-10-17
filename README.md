# GraphHacks — Agent with a Graph Context Layer

An agent where the knowledge graph shapes what the agent does, not just what it stores. Built with FalkorDB.

## Architecture

```
┌─────────────────┐  ┌─────────────┐  ┌──────────┐
│   Entry Points  │  │  Reasoning  │  │  Memory  │
│                 │  │             │  │          │
│  main.py (CLI)  │──► GraphReasoner ─► AgentMemory
│  api.py (REST)  │──►              ─►  (3-layer)
│  mcp_server.py  │──► GraphExplainer
│  (MCP/stdio)    │  │             │  │          │
└─────────────────┘  └──────┬──────┘  └──────────┘
                            │
                    ┌───────┴───────┐
                    │   Graph Layer │
                    │               │
                    │  GraphContext │  Abstract interface
                    │  (ABC)        │
                    │  ├── FalkorDB  │  Production (Docker)
                    │  └── InMemory   │  Dev/test (NetworkX)
                    └────────────────┘
```

## Quick Start

```bash
# Clone and set up
git clone https://github.com/kunalGupta5780/GraphHacks.git
cd GraphHacks
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt

# Verify everything works
python test_setup.py

# Run the 5-question demo
python main.py --demo

# Interactive chat
python main.py
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `python main.py` | Interactive REPL |
| `python main.py --demo` | Run built-in demo (5 questions) |
| `python main.py --ask "question"` | Ask a single question |
| `python main.py --seed` | Populate the graph and exit |
| `python main.py --user "alice"` | Isolate memory per user |

## REST API

```bash
python api.py
# or:
uvicorn api:app --reload
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | HTML UI |
| GET | `/api/status` | Backend info |
| POST | `/api/ask` | Ask a question (returns Answer DTO) |
| GET | `/api/graph` | Graph snapshot |
| GET | `/api/memory` | User memory summary |
| POST | `/api/seed` | Re-seed the graph |
| GET | `/docs` | OpenAPI docs |

## MCP Server

Exposes 8 graph tools for Claude Desktop, Cursor, or any MCP-compatible client:

```bash
python mcp_server.py
```

**Tools:** `ask_question`, `people_on_system`, `impact_analysis`, `who_knows`, `decision_trace`, `find_connection`, `graph_status`

## Docker

```bash
docker-compose up -d           # FalkorDB + FastAPI
# API at http://localhost:8000
# Auto docs at http://localhost:8000/docs
# FalkorDB at localhost:6379
```

## How It Works

The agent answers questions by traversing paths in the graph. Every answer includes:
- **Confidence score** (0%–100%)
- **Reasoning steps** (which queries traversed)
- **Path traces** (node → relationship → node chains)
- **Raw results** (structured data backing the answer)

### Example

**Question:** "Who has worked on the FalkorDB system?"

The reasoner traverses: `Person → WORKS_ON → Project → USES → System("FalkorDB")` and finds 4 people who worked on projects using FalkorDB.

## Project Structure

```
GraphHacks/
├── graph/
│   ├── base.py              # GraphContext ABC + dataclasses
│   ├── config.py            # get_graph() factory (FalkorDB → InMemory fallback)
│   ├── inmemory_context.py  # NetworkX backend (dev/test)
│   ├── falkordb_context.py  # FalkorDB backend (production)
│   ├── models.py            # Entity dataclasses + enums
│   └── seed_data.py         # Seed script (48 nodes, 58 edges)
├── agent/
│   ├── reasoner.py          # Core reasoning engine
│   ├── memory.py            # 3-layer graph-based memory
│   ├── explainer.py         # Human-readable output formatting
│   └── tools.py             # High-level graph utilities
├── main.py                  # CLI entry point
├── api.py                   # FastAPI REST server
├── mcp_server.py            # MCP server (stdio)
├── docker-compose.yml       # FalkorDB + API
├── Dockerfile               # Python 3.12 container
└── requirements.txt
```

## Dependencies

- **falkordb** — Real graph database client (Redis-based, Cypher-compatible)
- **networkx** — In-memory graph (fallback when FalkorDB unavailable)
- **mcp** — Model Context Protocol server
- **fastapi** + **uvicorn** — REST API server
- **pydantic** — Data validation

## License

MIT