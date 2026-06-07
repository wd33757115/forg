"""Tests for knowledge auto-extraction and memory graph."""

from __future__ import annotations

from forge.core.memory.graph import MemoryGraph
from forge.core.state import create_initial_state
from forge.utils.knowledge_extract import extract_reusable_knowledge


def test_extract_reusable_knowledge():
    state = create_initial_state("kb-extract")
    state["last_solution"] = {
        "problem_type": "security",
        "recommended_solution_id": "sol-a",
        "rule_pack_references": [{"rule_id": "db-001"}],
    }
    state["last_compliance_result"] = {"compliance_status": "partial"}
    state["compliance_retry_count"] = 1
    patch = extract_reusable_knowledge(state)
    assert len(patch["knowledge_base"]) == 1
    entry = patch["knowledge_base"][0]
    assert entry["type"] == "case"
    assert entry["outcome"] == "partial"
    assert "db-001" in entry["related_rules"]
    graph = patch.get("memory_graph") or {}
    assert graph.get("nodes")
    assert len(graph["nodes"]) >= 2


def test_memory_graph_from_entries():
    entries = [
        {
            "id": "kb-1",
            "content": "案例",
            "tags": ["security"],
            "related_rules": ["db-001"],
            "type": "case",
        }
    ]
    graph = MemoryGraph.from_knowledge_entries(entries)
    assert len(graph.nodes) >= 2
    assert len(graph.edges) == 1
