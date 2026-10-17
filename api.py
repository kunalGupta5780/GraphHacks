"""
FastAPI server for the GraphHacks agent.

Endpoints:
  GET  /              – landing page
  GET  /api/status    – backend info
  POST /api/ask       – ask a question (returns Answer DTO)
  GET  /api/graph     – graph snapshot
  GET  /api/memory    – user memory summary
  POST /api/seed      – re-seed the graph
  GET  /docs          – OpenAPI docs (FastAPI auto)
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from graph.config import get_graph
from graph.seed_data import seed
from agent.reasoner import GraphReasoner
from agent.explainer import GraphExplainer
from agent.memory import AgentMemory

BASE_DIR = __import__("pathlib").Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="GraphHacks Agent", description="Agent that acts on connected graph data")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Singleton instances
_ctx = None
_memory = None
_reasoner = None
_explainer = None


def _init():
    global _ctx, _memory, _reasoner, _explainer
    if _ctx is None:
        _ctx = get_graph()
        seed(_ctx)
        _memory = AgentMemory(_ctx)
        _reasoner = GraphReasoner(_ctx)
        _explainer = GraphExplainer()
    return _ctx, _memory, _reasoner, _explainer


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    params: dict[str, Any] = Field(default_factory=dict)


class AskResponse(BaseModel):
    question: str
    answer: str
    confidence: float
    confidence_reason: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[dict[str, Any]] = Field(default_factory=list)
    raw_results: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str = ""


@app.get("/", response_class=HTMLResponse)
def index():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8") if (STATIC_DIR / "index.html").exists() else "<h1>GraphHacks Agent</h1>"
    return HTMLResponse(content=html)


@app.get("/api/status")
def status():
    ctx, _, _, _ = _init()
    return {"backend": ctx.backend_name, "snapshot": ctx.save_snapshot()}


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    ctx, memory, reasoner, explainer = _init()
    memory.log_conversation("user", req.question)
    answer = reasoner.ask(req.question, req.params)
    memory.log_conversation("agent", answer.answer)

    return AskResponse(
        question=answer.question,
        answer=answer.answer,
        confidence=answer.confidence,
        confidence_reason=answer.confidence_reason,
        steps=[s.__dict__ for s in answer.steps],
        paths=answer.paths,
        raw_results=answer.raw_results,
        explanation=explainer.explain(answer, detail_level="full"),
    )


@app.get("/api/graph")
def graph_snapshot():
    ctx, _, _, _ = _init()
    return ctx.save_snapshot()


@app.get("/api/memory/{user_id}")
def memory_summary(user_id: str = "default"):
    ctx, memory, _, _ = _init()
    memory = AgentMemory(ctx, user_id)
    return memory.get_context()


@app.post("/api/seed")
def do_seed():
    ctx, _, _, _ = _init()
    seed(ctx)
    return {"status": "seeded", "snapshot": ctx.save_snapshot()}
