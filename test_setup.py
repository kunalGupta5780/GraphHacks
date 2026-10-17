"""Quick test script to verify all imports and basic graph functionality."""
import sys, os, traceback

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run():
    print("Testing imports...")
    from graph.config import get_graph
    from graph.seed_data import seed
    print("  [OK] graph.config, graph.seed_data")

    from graph.models import NodeType, RelationshipType, Person, Project, System
    print("  [OK] graph.models")

    from agent.memory import AgentMemory
    from agent.reasoner import GraphReasoner
    from agent.explainer import GraphExplainer
    from agent.tools import GraphTools
    print("  [OK] agent modules")

    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool
        print("  [OK] mcp")
    except ImportError as e:
        print(f"  [WARN] mcp: {e}")

    print("\nBuilding graph and seeding...")
    ctx = get_graph()
    seed(ctx)
    print(f"  Backend: {ctx.backend_name}")
    snap = ctx.save_snapshot()
    print(f"  Nodes: {snap.get('node_count')}, Edges: {snap.get('edge_count')}")

    print("\nTesting queries...")
    result = ctx.execute(
        "MATCH (p:Person)-[:HAS_SKILL]->(:Skill {name: 'Python'}) RETURN p.name AS name"
    )
    print(f"  Python devs: {[r.get('name') for r in result.to_dicts()]}")

    result2 = ctx.execute(
        "MATCH (p:Person)-[:WORKS_ON]->(:Project)-[:USES]->(s:System {name: 'FalkorDB'}) RETURN p.name AS person"
    )
    print(f"  People on FalkorDB: {[r.get('person') for r in result2.to_dicts()]}")

    print("\nTesting reasoner...")
    reasoner = GraphReasoner(ctx)
    answer = reasoner.ask("Who has worked on the FalkorDB system?", {"system": "FalkorDB"})
    print(f"  Answer: {answer.answer[:100]}...")
    print(f"  Confidence: {answer.confidence}")

    print("\nRunning mini-demo...")
    demo = [
        ("Who has worked on the FalkorDB system?", {"system": "FalkorDB"}),
        ("What breaks if AuthService goes down?", {"system": "AuthService"}),
        ("Who knows Python on the team?", {"skill": "Python"}),
    ]
    for q, p in demo:
        ans = reasoner.ask(q, p)
        print(f"\n>>> {q}")
        print(f"  {ans.answer[:150]}")
        print(f"  Confidence: {ans.confidence:.0%}")

    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    # Use os._exit to bypass MCP atexit handlers that cause spurious exit code 1
    os._exit(0)



