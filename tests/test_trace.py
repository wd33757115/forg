"""Tests for pipeline trace helpers."""

from __future__ import annotations

from forge.core.state import create_initial_state
from forge.utils.trace import summarize_agent_input, summarize_agent_output


def test_summarize_problem_solver_io():
    state = create_initial_state("trace-ps")
    state["messages"] = []
    state["problem_type_hint"] = "security"
    inp = summarize_agent_input(state, "problem_solver")
    assert "security" in inp
    updates = {
        "last_solution": {
            "recommended_solution_id": "sol-x",
            "problem_type": "security",
            "rule_pack_references": [{}, {}],
            "problem_analysis": "根因分析",
        }
    }
    out = summarize_agent_output(state, "problem_solver", updates)
    assert "sol-x" in out
    assert "refs=2" in out
