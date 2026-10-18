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

## Graph Data Model

The knowledge graph contains **11 node types** and **20 relationship types**, seeded with realistic company data (48 nodes, 58 edges).

### Node Types

| Node Type | Properties | Description |
|-----------|------------|-------------|
| `Person` | `name`, `role`, `team`, `email`, `skills`, `hire_date` | Team members |
| `Team` | `name`, `description` | Organizational teams |
| `Project` | `name`, `description`, `status`, `start_date`, `end_date` | Work initiatives |
| `System` | `name`, `type`, `criticality`, `owner`, `description` | Infrastructure/services |
| `Document` | `title`, `type`, `summary`, `created_by`, `created_date`, `url`, `content` | ADRs, specs, docs |
| `Decision` | `title`, `rationale`, `date`, `status`, `outcome` | Architectural decisions |
| `Meeting` | `title`, `date`, `agenda`, `notes` | Meetings and retros |
| `Ticket` | `title`, `description`, `status`, `priority`, `assignee`, `created_date` | Jira tickets |
| `Skill` | `name`, `category` | Technical skills |
| `Concept` | `name`, `description`, `confidence`, `source` | Learned concepts from conversations |
| `Conversation` / `Memory` | `content`, `speaker`, `timestamp`, `session_id`, `tags`, `confidence`, `source_query` | Agent memory layers |

### Relationship Types

| Relationship | Direction | Meaning |
|--------------|-----------|---------|
| `WORKS_ON` | Person → Project | Person works on a project |
| `MEMBER_OF` | Person → Team | Person belongs to a team |
| `HAS_SKILL` | Person → Skill | Person has a skill |
| `KNOWN_FOR` | Person → Concept | Person is known for a concept |
| `RAISED` | Person → Ticket | Person raised a ticket |
| `RESOLVED` | Person → Ticket | Person resolved a ticket |
| `OWNS` | Person → System | Person owns a system |
| `ATTENDED` | Person → Meeting | Person attended a meeting |
| `ASKED` | Person → Conversation | Person asked a question |
| `LEARNED` | Person → Memory | Person learned something |
| `USES` | Project → System | Project uses a system |
| `DEPENDS_ON` | System → System | System depends on another |
| `HAS_DOCUMENT` | Project/System → Document | Associated documentation |
| `HAS_DECISION` | Project → Decision | Decision belonging to project |
| `HAS_TICKET` | Project → Ticket | Tickets for a project |
| `HAS_MEETING` | Project → Meeting | Meetings for a project |
| `BASED_ON` | Decision → Document | Decision based on a document |
| `MADE_IN` | Decision → Meeting | Decision made in a meeting |
| `TRACKS` | Ticket → Decision | Ticket tracking a decision |
| `RELATED_TO` | Person ↔ Person / Concept ↔ Concept | General relationships |

## Key Cypher Queries

The agent traverses the graph using these core query patterns:

### 1. Multi-hop Reasoning (Person → Project → System)
```cypher
MATCH (p:Person)-[:WORKS_ON]->(proj:Project)-[:USES]->(s:System {name: 'FalkorDB'})
RETURN p.name AS person, count(*) AS projects ORDER BY projects DESC
```

### 2. Impact Analysis (Reverse Dependency)
```cypher
MATCH (dep)-[:DEPENDS_ON]->(s:System {name: 'FalkorDB'})
RETURN dep.name AS dependent, labels(dep) AS dep_type
```

### 3. Decision Trace (Decision → Document + Meeting)
```cypher
MATCH (d:Decision {title: 'topic'})-[:BASED_ON]->(doc:Document) RETURN doc
```
```cypher
MATCH (d:Decision {title: 'topic'})-[:MADE_IN]->(m:Meeting) RETURN m
```

### 4. Shortest Path Between Systems
```cypher
MATCH p=shortestPath((:System {name: 'AuthService'})-[:DEPENDS_ON*..10]-(n:System))
RETURN p
```

### 5. Who Knows a Skill
```cypher
MATCH (p:Person)-[:HAS_SKILL]->(s:Skill {name: 'Python'})
RETURN p.name AS name, p.role AS role, p.team AS team
```

### 6. Conversation Search
```cypher
MATCH (c:Conversation)
WHERE c.speaker CONTAINS 'name'
RETURN c.content, c.timestamp ORDER BY c.timestamp DESC LIMIT 10
```

### 7. General Keyword Search
```cypher
MATCH (n)
WHERE toLower(n.name) CONTAINS toLower('keyword')
   OR toLower(n.title) CONTAINS toLower('keyword')
RETURN n.name AS name, labels(n) AS labels
```

### 8. Graph Algorithms
```cypher
CALL algo.pageRank('Person', 'WORKS_ON', {topN: 5})
YIELD nodeId, score RETURN nodeId, score
```
```cypher
CALL algo.connectedComponents()
YIELD nodeId, component RETURN nodeId, component
```

## Demo Video

[![Watch the demo](https://img.youtube.com/vi/demo-thumbnail/0.jpg)](https://youtu.be/demo-link)

A 2-minute walkthrough of the live dashboard:
- Interactive graph visualization in the browser
- Live question answering with confidence scores
- Node inspection and property viewing
- Real-time graph statistics and label breakdowns

## Track

**Entering: Tracks 01, 02, and 03** — this project addresses all three hackathon tracks:

### Track 01 — Agents That Act on Connected Data
- ✅ **Multi-hop reasoning** — GraphReasoner orchestrates multi-hop traversals (Person → Project → System → Document)
- ✅ **Graph queries and algorithms as agent tools** — Cypher queries + PageRank + shortestPath + connected components
- ✅ **Tool selection through MCP** — `mcp_server.py` exposes 8 graph tools for any MCP-compatible client
- ✅ **Actions based on what the graph shows** — Every answer produces confidence scores, reasoning steps, and path traces back to source nodes
- ✅ **Explainable results** — GraphExplainer formats results with step-by-step reasoning chains and evidence

### Track 02 — Agent Memory and Coordination
- ✅ **Episodic, semantic, and procedural memory** — 3-layer graph-based memory stores conversations, decisions, and learned facts as graph nodes
- ✅ **Persistent conversation history** — Conversations and memories persist as `Conversation` and `Memory` nodes in the graph
- ✅ **Shared state and handoffs between agents** — All memory stored in the shared graph, accessible to all agents via GraphContext interface
- ✅ **High-concurrency reads and writes** — Backend-agnostic (FalkorDB supports concurrent Redis operations; InMemory uses NetworkX)
- ✅ **Separate memory per user or tenant** — CLI supports `--user` flag for per-user memory isolation

### Track 03 — Company Brain
- ✅ **Knowledge from docs, tickets, and chats in one graph** — All entities (48 nodes: people, teams, projects, systems, documents, decisions, meetings, tickets, skills) unified in one knowledge graph
- ✅ **Who owns what, and who knows what** — OWNS relationships link people to systems; HAS_SKILL links people to skills; USES links projects to systems
- ✅ **Tracing decisions back to their source** — Decision → BASED_ON → Document and Decision → MADE_IN → Meeting relationships trace every decision to its source
- ✅ **Keeping knowledge current as things change** — Live API (`/api/seed`) allows re-seeding; graph context auto-selects FalkorDB in production
- ✅ **Answers with clear sources** — Every answer includes path traces and raw results backing the claim

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