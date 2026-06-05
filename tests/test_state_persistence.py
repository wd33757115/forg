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
