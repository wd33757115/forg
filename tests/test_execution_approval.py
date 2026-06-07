"""Tests for execution layer and approval flow."""

from __future__ import annotations

from forge.core.approval.flow import run_approval_gate
from forge.core.execution.generator import generate_execution_tasks
from forge.core.state import create_initial_state


def test_generate_execution_tasks_from_gaps():
    state = create_initial_state("exec-test")
    state["last_compliance_result"] = {
        "missing_items": ["缺少审计日志", "未配置 MFA"],
        "risk_level": "high",
    }
    state["last_solution"] = {
        "recommended_solution_id": "sol-1",
        "rule_pack_references": [{"rule_id": "db-001"}],
    }
    tasks = generate_execution_tasks(state)
    assert len(tasks) >= 2
    assert tasks[0]["task_type"] == "remediation"


def test_approval_auto_execute():
    state = create_initial_state("apr-auto")
    state["execution_tasks"] = [{"id": "t1", "status": "draft", "title": "x"}]
    state["confidence_recommendation"] = "auto_execute"
    state["confidence_score"] = 0.9
    state["last_confidence_result"] = {"explanation": ["ok"]}
    out = run_approval_gate(state, auto_approve=False)
    assert out["approval_status"] == "auto_approved"
    assert out["execution_tasks"][0]["status"] == "ready"


def test_approval_needs_review_pending():
    state = create_initial_state("apr-pending")
    state["execution_tasks"] = [{"id": "t1", "status": "draft", "title": "x"}]
    state["confidence_recommendation"] = "needs_review"
    state["confidence_score"] = 0.55
    state["last_confidence_result"] = {"explanation": ["review"]}
    out = run_approval_gate(state)
    assert out["approval_status"] == "pending"
    assert len(out["pending_approvals"]) == 1


def test_approval_force_approve():
    state = create_initial_state("apr-force")
    state["execution_tasks"] = [{"id": "t1", "status": "draft", "title": "x"}]
    state["confidence_recommendation"] = "needs_review"
    state["confidence_score"] = 0.55
    state["pending_approvals"] = [{"id": "apr-1", "status": "pending"}]
    state["last_confidence_result"] = {"explanation": []}
    out = run_approval_gate(state, force_approve=True)
    assert out["approval_status"] == "approved"
