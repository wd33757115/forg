"""Feedback loop — write execution / approval outcomes to knowledge_base."""

from __future__ import annotations

from typing import Any

from forge.core.state import ProjectState
from forge.utils.knowledge import append_knowledge, append_knowledge_to_state


def record_approval_feedback(state: ProjectState, approval_status: str) -> dict[str, Any]:
    """Persist approval outcome as reusable project knowledge."""
    requests = state.get("approval_requests") or []
    if not requests:
        return {}
    last = requests[-1]
    outcome = "approved" if approval_status in ("approved", "auto_approved") else (
        "rejected" if approval_status == "rejected" else approval_status
    )
    problem_type = state.get("problem_type") or (state.get("last_solution") or {}).get("problem_type", "general")
    summary = (
        f"审批结果={approval_status} | 置信度={last.get('confidence_score', '—')} | "
        f"建议={last.get('recommendation', '—')}"
    )
    entry = append_knowledge(
        state,
        agent="approval_gate",
        summary=summary,
        tags=[problem_type, "approval", outcome],
        category="feedback",
        detail={
            "type": "approval_outcome",
            "outcome": outcome,
            "approval_status": approval_status,
            "confidence_score": last.get("confidence_score"),
            "problem_type": problem_type,
        },
    )
    entry["type"] = "feedback"
    entry["outcome"] = outcome
    return append_knowledge_to_state(state, entry)


def record_execution_feedback(state: ProjectState) -> dict[str, Any]:
    """Persist execution results (or ready tasks) to knowledge_base for history_factor."""
    results = state.get("execution_results") or []
    tasks = state.get("execution_tasks") or []
    problem_type = state.get("problem_type") or (state.get("last_solution") or {}).get("problem_type", "general")

    if results:
        successes = sum(1 for r in results if r.get("status") == "success")
        outcome = "success" if successes == len(results) else (
            "partial" if successes else "failed"
        )
        titles = "; ".join((r.get("summary") or "")[:40] for r in results[:3])
        summary = f"执行完成 {successes}/{len(results)} 成功 | {titles}"
        entry = append_knowledge(
            state,
            agent="execution",
            summary=summary,
            tags=[problem_type, "execution", outcome],
            category="feedback",
            detail={
                "type": "execution_outcome",
                "task_count": len(results),
                "success_count": successes,
                "task_ids": [r.get("task_id") for r in results[:8]],
                "problem_type": problem_type,
                "backend": (results[0].get("metadata") or {}).get("backend"),
            },
        )
        entry["type"] = "feedback"
        entry["outcome"] = outcome
        return append_knowledge_to_state(state, entry)

    ready = [t for t in tasks if t.get("status") in ("ready", "executed")]
    if not ready:
        return {}
    titles = "; ".join(t.get("title", "")[:40] for t in ready[:3])
    summary = f"执行任务 {len(ready)} 项就绪 | {titles}"
    entry = append_knowledge(
        state,
        agent="execution",
        summary=summary,
        tags=[problem_type, "execution", "ready"],
        category="feedback",
        detail={
            "type": "execution_outcome",
            "task_count": len(ready),
            "task_ids": [t.get("id") for t in ready[:8]],
            "problem_type": problem_type,
        },
    )
    entry["type"] = "feedback"
    entry["outcome"] = "ready"
    return append_knowledge_to_state(state, entry)


def apply_feedback_loop(state: ProjectState, *, approval_status: str | None = None) -> dict[str, Any]:
    """Merge approval + execution feedback into state knowledge_base."""
    merged: dict[str, Any] = dict(state)
    status = approval_status or state.get("approval_status")
    if status:
        merged.update(record_approval_feedback(merged, status))
    exec_patch = record_execution_feedback(merged)
    if exec_patch:
        merged.update(exec_patch)
    kb = merged.get("knowledge_base")
    return {"knowledge_base": kb} if kb is not None and kb != state.get("knowledge_base") else {}
