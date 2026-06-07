"""LangGraph approval gate node."""

from __future__ import annotations

from typing import Any

from forge.core.approval.flow import run_approval_gate
from forge.core.execution.backend import run_task_execution
from forge.core.state import ProjectState
from forge.utils.conversation import record_conversation
from forge.utils.feedback_loop import apply_feedback_loop
from forge.utils.trace import append_pipeline_trace, summarize_agent_input, summarize_agent_output


def approval_gate_node(state: ProjectState) -> dict[str, Any]:
    """Gate execution tasks on confidence / manual approval."""
    auto = bool(state.get("auto_approve"))
    force = state.get("_force_approval")
    force_approve: bool | None = None
    if force in ("approve", "approved", True):
        force_approve = True
    elif force in ("reject", "rejected", False):
        force_approve = False

    result = run_approval_gate(state, auto_approve=auto, force_approve=force_approve)
    status = result.get("approval_status", "pending")
    updates: dict[str, Any] = dict(result)
    updates.update(
        record_conversation(
            state,
            agent="approval_gate",
            event="approval_decision",
            summary=f"审批状态: {status}",
            detail={
                "approval_status": status,
                "pending_count": len(result.get("pending_approvals") or []),
            },
        )
    )
    output_summary = summarize_agent_output(state, "approval_gate", updates)
    updates["pipeline_trace"] = append_pipeline_trace(
        state,
        {
            "agent": "approval_gate",
            "status": "success",
            "input_summary": summarize_agent_input(state, "approval_gate"),
            "output_summary": output_summary,
            "detail": output_summary,
        },
    )
    if status in ("approved", "auto_approved"):
        tasks, exec_results = run_task_execution(updates.get("execution_tasks") or [], state)
        if exec_results:
            updates["execution_tasks"] = tasks
            updates["execution_results"] = list(state.get("execution_results") or []) + exec_results

    updates.update(apply_feedback_loop({**state, **updates}, approval_status=status))
    return updates
