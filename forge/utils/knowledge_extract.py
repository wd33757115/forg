"""Auto-extract reusable knowledge after pipeline finalize."""

from __future__ import annotations

from typing import Any

from forge.core.state import ProjectState
from forge.utils.knowledge import append_knowledge, append_knowledge_to_state
from forge.utils.knowledge_memory import rebuild_memory_graph
from forge.core.memory.manager import ProjectMemory, apply_memory_patch  # M0 durable memory


def extract_reusable_knowledge(state: ProjectState) -> dict[str, Any]:
    """
    Extract a session summary entry into knowledge_base after successful run.

    M0 memory persistence: also uses ProjectMemory to:
    - Ingest recent execution outcomes as durable episodic→semantic memory (makes D3 closed loop survive runs).
    - Produce a consistent graph via the manager.

    Returns state patch with new knowledge entries + memory_graph.
    """
    solution = state.get("last_solution") or {}
    compliance = state.get("last_compliance_result") or {}
    exec_results = state.get("execution_results") or []

    if not solution and not compliance and not exec_results:
        return {}

    problem_type = solution.get("problem_type") or state.get("problem_type") or "general"
    comp_status = compliance.get("compliance_status", compliance.get("overall_status", "unknown"))
    outcome = "success" if comp_status in ("compliant", "pass") else (
        "partial" if comp_status in ("partial", "gaps_found") else "failed"
    )

    refs = solution.get("rule_pack_references") or []
    related_rules = [r.get("rule_id") for r in refs if r.get("rule_id")]

    # Use the manager for durable accumulation (Grok-style write-back)
    mem = ProjectMemory.from_state(state)

    # 1) The session summary case (existing behavior, now through manager for consistency)
    if solution or compliance:
        summary = (
            f"[{problem_type}] {solution.get('recommended_solution_id', '方案')} "
            f"| 合规={comp_status} | 重试={state.get('compliance_retry_count', 0)}"
        )
        mem.append_case(
            summary=summary,
            tags=[problem_type, "session_summary", outcome],
            related_rules=related_rules,
            outcome=outcome,
            source="forge_finalize",
            detail={
                "problem_type": problem_type,
                "compliance_status": comp_status,
                "confidence_score": state.get("confidence_score"),
            },
        )

    # 2) M0: turn recent execution results into durable memory entries (D3 closed-loop now cross-run)
    for res in exec_results[-3:]:  # last few to keep memory bounded
        mem.append_execution_outcome(
            task_id=str(res.get("task_id", "?")),
            status=str(res.get("status", "unknown")),
            summary=str(res.get("summary") or "")[:200],
            problem_type=problem_type,
            related_solution_id=(solution.get("recommended_solution_id") if solution else None),
        )

    # Manager holds the authoritative kb + graph for this project
    patch = mem.to_state_patch()
    # Also keep the classic kb_update shape for any direct consumers
    # (we already mutated via manager, so the patch is the source of truth)
    return apply_memory_patch(state, patch)
