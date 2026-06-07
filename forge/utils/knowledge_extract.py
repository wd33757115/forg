"""Auto-extract reusable knowledge after pipeline finalize."""

from __future__ import annotations

from typing import Any

from forge.core.state import ProjectState
from forge.utils.knowledge import append_knowledge, append_knowledge_to_state
from forge.utils.knowledge_memory import rebuild_memory_graph


def extract_reusable_knowledge(state: ProjectState) -> dict[str, Any]:
    """
    Extract a session summary entry into knowledge_base after successful run.

    Returns state patch with new knowledge entry and optional memory_graph snapshot.
    """
    solution = state.get("last_solution") or {}
    compliance = state.get("last_compliance_result") or {}
    if not solution and not compliance:
        return {}

    problem_type = solution.get("problem_type") or state.get("problem_type") or "general"
    comp_status = compliance.get("compliance_status", compliance.get("overall_status", "unknown"))
    outcome = "success" if comp_status in ("compliant", "pass") else (
        "partial" if comp_status in ("partial", "gaps_found") else "failed"
    )

    refs = solution.get("rule_pack_references") or []
    related_rules = [r.get("rule_id") for r in refs if r.get("rule_id")]

    summary = (
        f"[{problem_type}] {solution.get('recommended_solution_id', '方案')} "
        f"| 合规={comp_status} | 重试={state.get('compliance_retry_count', 0)}"
    )
    entry = append_knowledge(
        state,
        agent="forge_finalize",
        summary=summary,
        tags=[problem_type, "session_summary", outcome],
        category="session",
        detail={
            "problem_type": problem_type,
            "compliance_status": comp_status,
            "confidence_score": state.get("confidence_score"),
        },
    )
    entry["type"] = "case"
    entry["related_rules"] = related_rules
    entry["outcome"] = outcome

    kb_update = append_knowledge_to_state(state, entry)
    return {**kb_update, "memory_graph": rebuild_memory_graph(kb_update["knowledge_base"])}
