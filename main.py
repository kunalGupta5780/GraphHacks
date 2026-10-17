"""
CLI entry point for the GraphHacks agent.

Usage:
    python main.py                    # interactive REPL
    python main.py --seed             # seed the graph and exit
    python main.py --ask "question"   # ask a single question
    python main.py --demo             # run the built-in demo
"""

from __future__ import annotations

import sys
import json
import argparse
from datetime import datetime

from graph.config import get_graph
from graph.seed_data import seed
from agent.reasoner import GraphReasoner
from agent.explainer import GraphExplainer
from agent.memory import AgentMemory


def build_agent(user_id: str = "default"):
    """Create graph context, memory, reasoner, and explainer."""
    ctx = get_graph()
    memory = AgentMemory(ctx, user_id)
    reasoner = GraphReasoner(ctx)
    explainer = GraphExplainer()
    return ctx, memory, reasoner, explainer


def run_demo(reasoner: GraphReasoner, explainer: GraphExplainer, memory: AgentMemory) -> None:
    """Run a built-in demo showing all three tracks."""
    demo_questions = [
        ("Who has worked on the FalkorDB system?", {"system": "FalkorDB"}),
        ("What breaks if AuthService goes down?", {"system": "AuthService"}),
        ("Tell me about the decision to use FalkorDB", {"decision": "ADR-001: Choose FalkorDB for Knowledge Graph"}),
        ("Who knows Python on the team?", {"skill": "Python"}),
        ("What did Carol ask for recently?", {"person": "Carol Kim"}),
    ]

    print("=" * 70)
    print("GraphHacks Agent — Company Brain Demo")
    print("=" * 70)
    print()

    for question, params in demo_questions:
        print(f"\n>>> {question}")
        print("-" * 50)
        answer = reasoner.ask(question, params)
        explanation = explainer.explain(answer, detail_level="full")
        print(explanation)

        # Store in memory
        memory.log_conversation("user", question)
        memory.log_conversation("agent", answer.answer)
        memory.remember_fact(
            concept_name=f"Answer: {question[:40]}",
            description=answer.answer[:300],
            source=answer.confidence_reason,
            tags=["demo", "qa"],
        )
        print()


def interactive_loop(ctx, reasoner: GraphReasoner, explainer: GraphExplainer,
                     memory: AgentMemory) -> None:
    """Interactive REPL."""
    print(f"GraphHacks Agent — running on [{ctx.backend_name}]")
    print(f"Session ID: {memory.session_id}")
    print("Type 'quit' or 'exit' to leave.\n")

    while True:
        try:
            question = input("? ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        memory.log_conversation("user", question)
        answer = reasoner.ask(question)
        memory.log_conversation("agent", answer.answer)

        detail = "full" if "--detail" in question else "full"
        print()
        print(explainer.explain(answer, detail_level=detail))
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphHacks agent")
    parser.add_argument("--seed", action="store_true", help="Seed the graph with sample data")
    parser.add_argument("--ask", type=str, help="Ask a single question")
    parser.add_argument("--demo", action="store_true", help="Run the built-in demo")
    parser.add_argument("--user", type=str, default="default", help="User ID for memory isolation")
    args = parser.parse_args()

    ctx, memory, reasoner, explainer = build_agent(args.user)

    if args.seed:
        seed(ctx)
        print(f"Graph seeded on {ctx.backend_name}")
        snap = ctx.save_snapshot()
        print(json.dumps(snap, indent=2))
        return

    if args.demo:
        seed(ctx)
        run_demo(reasoner, explainer, memory)
        return

    if args.ask:
        seed(ctx)
        answer = reasoner.ask(args.ask)
        print(explainer.explain(answer, detail_level="full"))
        return

    # Interactive mode
    seed(ctx)
    interactive_loop(ctx, reasoner, explainer, memory)


if __name__ == "__main__":
    main()
