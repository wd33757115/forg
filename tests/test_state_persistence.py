"""Tests for ProjectState JSON persistence."""

import json
from pathlib import Path

from langchain_core.messages import HumanMessage

from forge.core import create_initial_state
from forge.utils.state_persistence import load_state, save_state


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
    assert raw["version"] == 1
