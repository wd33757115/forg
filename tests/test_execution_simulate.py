"""Tests for simulated execution."""

from __future__ import annotations

from forge.core.execution.simulate import simulate_execution


def test_simulate_execution_ready_tasks():
    tasks = [
        {"id": "t1", "status": "ready", "title": "整改A", "task_type": "remediation"},
        {"id": "t2", "status": "draft", "title": "草稿"},
    ]
    updated, results = simulate_execution(tasks)
    assert updated[0]["status"] == "executed"
    assert updated[1]["status"] == "draft"
    assert len(results) == 1
    assert results[0]["task_id"] == "t1"
