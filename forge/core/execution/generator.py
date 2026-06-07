"""Generate execution tasks from pipeline artifacts (v1.1 base layer)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from forge.core.execution.models import ExecutionTask
from forge.core.state import ProjectState


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_execution_tasks(state: ProjectState) -> list[dict[str, Any]]:
    """
    Build remediation / change-request drafts from compliance gaps and PM actions.

    Does not call external systems — content only.
    """
    tasks: list[dict[str, Any]] = []
    compliance = state.get("last_compliance_result") or {}
    pm = state.get("last_pm_advice") or {}
    solution = state.get("last_solution") or {}
    run_id = state.get("run_id", "run")

    for i, item in enumerate((compliance.get("missing_items") or [])[:5]):
        tasks.append(
            ExecutionTask(
                id=f"exec-{run_id}-rem-{i}",
                task_type="remediation",
                title=f"整改: {str(item)[:80]}",
                description=str(item),
                status="draft",
                priority="P1" if compliance.get("risk_level") in ("high", "critical") else "P2",
                source="compliance",
                related_rules=_rules_from_solution(solution),
                created_at=_utc_now(),
            ).to_state_dict()
        )

    for i, action in enumerate((pm.get("action_items") or [])[:5]):
        tasks.append(
            ExecutionTask(
                id=f"exec-{run_id}-pm-{i}",
                task_type="project_action",
                title=action.get("title", "PM 行动项"),
                description=action.get("description", action.get("title", "")),
                status="draft",
                priority=action.get("priority", "P2"),
                source="pm_advisor",
                created_at=_utc_now(),
            ).to_state_dict()
        )

    if not tasks and solution.get("recommended_solution_id"):
        tasks.append(
            ExecutionTask(
                id=f"exec-{run_id}-sol-0",
                task_type="implementation_wbs",
                title=f"实施方案: {solution.get('recommended_solution_id')}",
                description=(solution.get("problem_analysis") or "")[:500],
                status="draft",
                source="problem_solver",
                related_rules=_rules_from_solution(solution),
                created_at=_utc_now(),
            ).to_state_dict()
        )

    return tasks


def _rules_from_solution(solution: dict[str, Any]) -> list[str]:
    refs = solution.get("rule_pack_references") or []
    return [r.get("rule_id", "") for r in refs if r.get("rule_id")][:8]


def apply_execution_status(
    tasks: list[dict[str, Any]],
    *,
    recommendation: str,
    approved: bool,
) -> list[dict[str, Any]]:
    """Update task status based on approval outcome."""
    updated = []
    for t in tasks:
        copy = dict(t)
        if recommendation == "block":
            copy["status"] = "blocked"
        elif recommendation == "auto_execute" or approved:
            copy["status"] = "ready"
        else:
            copy["status"] = "pending_approval"
        updated.append(copy)
    return updated
