"""Tests for execution/approval feedback loop."""

from __future__ import annotations

from forge.core.state import create_initial_state
from forge.utils.feedback_loop import apply_feedback_loop, record_approval_feedback


def test_record_approval_feedback():
    state = create_initial_state("fb-1")
    state["approval_requests"] = [
        {"confidence_score": 0.6, "recommendation": "needs_review"},
    ]
    state["problem_type"] = "security"
    patch = record_approval_feedback(state, "approved")
    assert len(patch["knowledge_base"]) == 1
    assert patch["knowledge_base"][0]["type"] == "feedback"
    assert "approval" in patch["knowledge_base"][0]["tags"]


def test_apply_feedback_loop_with_execution():
    state = create_initial_state("fb-2")
    state["approval_requests"] = [{"confidence_score": 0.8, "recommendation": "auto_execute"}]
    state["execution_tasks"] = [{"id": "t1", "status": "ready", "title": "整改A"}]
    state["problem_type"] = "security"
    patch = apply_feedback_loop(state, approval_status="auto_approved")
    assert len(patch.get("knowledge_base", [])) >= 1


def test_execution_results_feedback_outcome():
    from forge.utils.feedback_loop import record_execution_feedback

    state = create_initial_state("fb-exec")
    state["problem_type"] = "security"
    state["execution_results"] = [
        {"task_id": "t1", "status": "success", "summary": "完成", "metadata": {"backend": "simulate"}},
        {"task_id": "t2", "status": "failed", "summary": "失败"},
    ]
    patch = record_execution_feedback(state)
    entry = patch["knowledge_base"][-1]
    assert entry["outcome"] == "partial"
    assert "execution" in entry["tags"]
