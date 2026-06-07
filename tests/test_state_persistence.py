"""Tests for ProjectState JSON persistence."""

import json
from pathlib import Path

from langchain_core.messages import HumanMessage

from forge.core import create_initial_state
from forge.utils.state_persistence import (
    load_state,
    load_state_with_metadata,
    prepare_state_for_run,
    save_state,
)


def test_save_and_load_state(tmp_path: Path):
    state = create_initial_state("persist-test", current_phase="implementation")
    state["messages"] = [HumanMessage(content="测试问题")]
    state["last_solution"] = {"recommended_solution_id": "sol-a"}
    state["compliance_retry_count"] = 1

    path = tmp_path / "session.json"
    save_state(state, path)
    assert path.exists()

    loaded = load_state(path)
    assert loaded["project_id"] == "persist-test"
    assert loaded["compliance_retry_count"] == 1
    assert loaded["last_solution"]["recommended_solution_id"] == "sol-a"
    assert len(loaded["messages"]) == 1
    assert "测试问题" in str(loaded["messages"][0].content)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 2
    assert raw["metadata"]["project_id"] == "persist-test"


def test_prepare_state_for_run_preserves_knowledge(tmp_path: Path):
    state = create_initial_state("resume-test")
    state["knowledge_base"] = [{"id": "kb-1", "category": "test", "content": "记忆"}]
    state["last_solution"] = {"recommended_solution_id": "old"}

    path = tmp_path / "resume.json"
    save_state(state, path, metadata={"last_question": "旧问题"})

    loaded, _ = load_state_with_metadata(path)
    prepared = prepare_state_for_run(loaded, "新问题", protection_level="3")

    assert len(prepared["knowledge_base"]) == 1
    assert prepared["last_solution"] is None
    assert prepared["run_id"]
    assert any("新问题" in str(m.content) for m in prepared["messages"])


def test_m0_memory_graph_durable_across_runs(tmp_path: Path):
    """M0 persistence: memory_graph (project memory) survives prepare and enables cross-run retrieval."""
    from forge.utils.knowledge_memory import rebuild_memory_graph
    from forge.core.memory.manager import ProjectMemory

    state = create_initial_state("mem-durable")
    # Seed a prior case (like a previous finalize would have done)
    kb_entry = {
        "id": "kb-prior-1",
        "category": "case",
        "content": "等保登录401曾用重置密码+审计加固解决",
        "source": "forge_finalize",
        "tags": ["security", "session_summary", "success"],
        "type": "case",
        "related_rules": ["db-acs-001"],
        "outcome": "success",
    }
    state["knowledge_base"] = [kb_entry]
    state["memory_graph"] = rebuild_memory_graph(state["knowledge_base"])

    path = tmp_path / "mem.json"
    save_state(state, path)

    loaded, _ = load_state_with_metadata(path)
    # prepare (new run) should carry the graph (M0 change)
    prepared = prepare_state_for_run(loaded, "新的登录401问题", protection_level="3")

    assert prepared.get("memory_graph") is not None
    assert any(n.get("node_type") == "rule" and n.get("label") == "db-acs-001" for n in (prepared["memory_graph"].get("nodes") or []))

    # Manager can retrieve the prior case with graph boost
    mem = ProjectMemory.from_state(prepared)
    hits = mem.search_similar_cases(problem_type="security", problem_text="登录401认证失败", limit=3)
    assert len(hits) >= 1
    # The prior success case should be findable (tag + rule overlap)
    assert any("db-acs" in str(h.get("related_rules", [])) or "401" in str(h.get("content", "")) for h in hits)
