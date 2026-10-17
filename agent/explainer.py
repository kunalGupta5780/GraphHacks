"""
Explainable results generator.

Turns the structured ``Answer`` from ``GraphReasoner`` into
human-readable explanations, JSON reports, and trace visualizations.
"""

from __future__ import annotations

import json
from typing import Any

from .reasoner import Answer, ReasoningStep


class GraphExplainer:
    """Formats agent answers with full provenance."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------ #
    # Text output
    # ------------------------------------------------------------------ #

    def explain(self, answer: Answer, detail_level: str = "full") -> str:
        """Produce a human-readable explanation of how the answer was derived."""
        lines: list[str] = []

        lines.append(f"## Answer\n\n{answer.answer}\n")

        if detail_level in ("full", "conf"):
            lines.append(f"**Confidence:** {answer.confidence:.0%}")
            lines.append(f"**Reason:** {answer.confidence_reason}\n")

        if detail_level == "full" and answer.steps:
            lines.append("## Reasoning Steps\n")
            for i, step in enumerate(answer.steps, 1):
                lines.append(f"{i}. **{step.action}** – {step.description}")
                lines.append(f"   - Query: `{step.query}`")
                lines.append(f"   - Result: {step.result_summary}")
                if step.evidence:
                    lines.append(f"   - Evidence: {json.dumps(step.evidence[:2], indent=2)[:300]}")
                lines.append("")

        if detail_level == "full" and answer.paths:
            lines.append("## Path Traces\n")
            for i, path in enumerate(answer.paths, 1):
                desc = path.get("description", "")
                if desc:
                    lines.append(f"Path {i}: {desc}\n")
                    steps = path.get("steps", [])
                    for j, s in enumerate(steps):
                        node = s.get("node", {})
                        rel = s.get("relationship")
                        node_name = node.get("properties", {}).get("name", node.get("properties", {}).get("title", ""))
                        labels = ":".join(node.get("labels", []))
                        if rel:
                            lines.append(f"  {j}. (:{labels} {{name: {node_name}}})")
                            lines.append(f"     -[:{rel['type']}]->")
                        else:
                            lines.append(f"  {j}. (:{labels} {{name: {node_name}}})")
                lines.append("")

        if detail_level == "full" and answer.raw_results:
            lines.append("## Raw Results\n")
            lines.append("```json")
            lines.append(json.dumps(answer.raw_results[:3], indent=2))
            lines.append("```")

        return "\n".join(lines)

    def explain_json(self, answer: Answer) -> str:
        """Return the answer as a structured JSON document."""
        return json.dumps(answer.to_dict(), indent=2, default=str)

    def explain_minimal(self, answer: Answer) -> str:
        """Return just the answer + confidence, no steps."""
        return f"{answer.answer}\n\n_Confidence: {answer.confidence:.0%} – {answer.confidence_reason}_"

    # ------------------------------------------------------------------ #
    # Summary for memory
    # ------------------------------------------------------------------ #

    def to_memory_entry(self, answer: Answer) -> str:
        """Summarise an answer so it can be stored as a memory fact."""
        return (
            f"Q: {answer.question}\n"
            f"A: {answer.answer[:200]}\n"
            f"Confidence: {answer.confidence:.0%}\n"
            f"Source: {answer.confidence_reason}"
        )
