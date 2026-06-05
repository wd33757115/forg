"""Tests for knowledge_base helpers."""

from __future__ import annotations

from forge.core.state import create_initial_state
from forge.utils.knowledge import append_knowledge, format_knowledge_context, search_knowledge


def test_append_and_search_by_tag():
    state = create_initial_state("kb-test")
    entry = append_knowledge(
        state,
        agent="problem_solver",
        summary="等保401故障已修复",
        tags=["security", "resolved"],
        category="case",
    )
    state["knowledge_base"] = [entry]
    found = search_knowledge(state, tags=["security"])
    assert len(found) == 1
    assert found[0]["content"].startswith("等保")


def test_search_by_agent():
    state = create_initial_state("kb-agent")
    state["knowledge_base"] = [
        append_knowledge(state, agent="compliance", summary="a", tags=["x"]),
        append_knowledge(state, agent="problem_solver", summary="b", tags=["x"]),
    ]
    found = search_knowledge(state, agent="compliance")
    assert len(found) == 1
    assert found[0]["source"] == "compliance"


def test_format_knowledge_context_empty():
    assert "无相关" in format_knowledge_context([])
