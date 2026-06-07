"""Tests for knowledge memory closed-loop helpers."""

from __future__ import annotations

from forge.core.memory.graph import MemoryGraph
from forge.core.state import create_initial_state
from forge.utils.knowledge import append_knowledge, append_knowledge_to_state
from forge.utils.knowledge_memory import (
    extract_rule_ids_from_text,
    format_memory_context,
    rebuild_memory_graph,
    search_similar_cases,
)


def test_extract_rule_ids_from_text():
    text = "对照 db-acs-001 与 itil-inc-001 处置"
    assert extract_rule_ids_from_text(text) == ["db-acs-001", "itil-inc-001"]


def test_rebuild_memory_graph_full_kb():
    entries = [
        {
            "id": "kb-1",
            "content": "案例A",
            "tags": ["security"],
            "related_rules": ["db-acs-001"],
            "type": "case",
        },
        {
            "id": "kb-2",
            "content": "案例B",
            "tags": ["security"],
            "related_rules": ["db-aud-001"],
            "type": "case",
        },
    ]
    graph = rebuild_memory_graph(entries)
    assert len(graph["nodes"]) >= 4
    assert len(graph["edges"]) == 2


def test_search_similar_cases_graph_boost():
    state = create_initial_state("mem-search")
    entry = append_knowledge(
        state,
        agent="forge_finalize",
        summary="历史401已修复",
        tags=["security", "session_summary"],
        category="session",
    )
    entry["outcome"] = "success"
    entry["related_rules"] = ["db-acs-001"]
    state.update(append_knowledge_to_state(state, entry))
    state["memory_graph"] = MemoryGraph.from_knowledge_entries(state["knowledge_base"]).to_dict()

    hits = search_similar_cases(
        state,
        problem_type="security",
        problem_text="登录401 请对照 db-acs-001",
        limit=2,
    )
    assert hits
    assert hits[0]["id"] == entry["id"]


def test_format_memory_context_shows_outcome():
    text = format_memory_context([{"source": "execution", "tags": ["security"], "outcome": "success", "content": "ok"}])
    assert "outcome=success" in text
