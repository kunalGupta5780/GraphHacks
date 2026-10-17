"""
MCP (Model Context Protocol) server for the GraphHacks agent.

Exposes graph query tools so that any MCP-compatible agent client
can use the graph as its context layer.

Run:  python mcp_server.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool
from mcp.server import NotificationOptions

from graph.config import get_graph
from graph.seed_data import seed
from agent.reasoner import GraphReasoner
from agent.explainer import GraphExplainer
from agent.tools import GraphTools

# Initialise once
_ctx = get_graph()
seed(_ctx)
_reasoner = GraphReasoner(_ctx)
_explainer = GraphExplainer()
_tools = GraphTools(_ctx)

server = Server("graphhacks")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(name="ask_question",
             description="Ask the agent a question requiring graph traversal.",
             inputSchema={"type": "object", "properties": {
                 "question": {"type": "string"},
                 "params": {"type": "object"},
             }, "required": ["question"]}),
        Tool(name="people_on_system",
             description="Who worked on projects using a given system.",
             inputSchema={"type": "object", "properties": {
                 "system_name": {"type": "string"},
             }, "required": ["system_name"]}),
        Tool(name="impact_analysis",
             description="What depends on a given system.",
             inputSchema={"type": "object", "properties": {
                 "system_name": {"type": "string"},
             }, "required": ["system_name"]}),
        Tool(name="who_knows",
             description="Who has a given skill.",
             inputSchema={"type": "object", "properties": {
                 "skill": {"type": "string"},
             }, "required": ["skill"]}),
        Tool(name="decision_trace",
             description="Trace a decision to source documents and meetings.",
             inputSchema={"type": "object", "properties": {
                 "decision_title": {"type": "string"},
             }, "required": ["decision_title"]}),
        Tool(name="find_connection",
             description="Shortest path between two entities.",
             inputSchema={"type": "object", "properties": {
                 "source": {"type": "string"},
                 "target": {"type": "string"},
             }, "required": ["source", "target"]}),
        Tool(name="graph_status",
             description="Get graph backend info and counts.",
             inputSchema={"type": "object", "properties": {}, "required": []}),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> str:
    args = arguments or {}

    if name == "graph_status":
        return json.dumps(_ctx.save_snapshot(), indent=2)

    if name == "ask_question":
        question = args["question"]
        params = args.get("params", {})
        answer = _reasoner.ask(question, params)
        return json.dumps({
            "question": answer.question,
            "answer": answer.answer,
            "confidence": answer.confidence,
            "confidence_reason": answer.confidence_reason,
            "explanation": _explainer.explain(answer, detail_level="full"),
            "steps": [s.__dict__ for s in answer.steps],
            "paths": answer.paths,
        }, indent=2, default=str)

    if name == "people_on_system":
        result = _ctx.execute(
            f"MATCH (p:Person)-[:WORKS_ON]->(:Project)-[:USES]->"
            f"(s:System {{name: '{args['system_name']}'}})"
            f" RETURN p.name AS person, p.team AS team, p.role AS role"
        )
        return json.dumps(result.to_dicts(), indent=2)

    if name == "impact_analysis":
        result = _ctx.execute(
            f"MATCH (dep)-[:DEPENDS_ON]->(s:System {{name: '{args['system_name']}'}})"
            f" RETURN dep.name AS dependent, labels(dep) AS types"
        )
        return json.dumps(result.to_dicts(), indent=2)

    if name == "who_knows":
        result = _ctx.execute(
            f"MATCH (p:Person)-[:HAS_SKILL]->(s:Skill)"
            f" WHERE toLower(s.name) CONTAINS toLower('{args['skill']}')"
            f" RETURN p.name AS person, p.team AS team, p.role AS role"
        )
        return json.dumps(result.to_dicts(), indent=2)

    if name == "decision_trace":
        trace = _tools.decision_trace(args["decision_title"])
        return json.dumps(trace, indent=2)

    if name == "find_connection":
        path = _tools.find_connection(args["source"], args["target"])
        if path:
            return json.dumps(path, indent=2)
        return f"No connection found between '{args['source']}' and '{args['target']}'"

    return f"Unknown tool: {name}"


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, NotificationOptions())


if __name__ == "__main__":
    asyncio.run(main())