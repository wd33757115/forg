"""LangGraph execution layer node."""

from __future__ import annotations

from typing import Any

from forge.core.confidence import ConfidenceScorer
from forge.core.execution.generator import generate_execution_tasks
from forge.core.state import ProjectState
from forge.utils.conversation import record_conversation


def execution_node(state: ProjectState) -> dict[str, Any]:
    """Generate execution tasks and compute confidence before approval gate."""
    tasks = generate_execution_tasks(state)
    scorer = ConfidenceScorer()
    confidence = scorer.score(dict(state))

    updates: dict[str, Any] = {
        "execution_tasks": tasks,
        "confidence_score": confidence.score,
        "confidence_level": confidence.level,
        "confidence_recommendation": confidence.recommendation,
        "last_confidence_result": {
            "score": confidence.score,
            "level": confidence.level,
            "recommendation": confidence.recommendation,
            "factors": {
                "compliance_factor": confidence.factors.compliance_factor,
                "evidence_factor": confidence.factors.evidence_factor,
                "history_factor": confidence.factors.history_factor,
                "retry_penalty": confidence.factors.retry_penalty,
                "error_penalty": confidence.factors.error_penalty,
            },
            "explanation": confidence.explanation,
        },
    }
    updates.update(
        record_conversation(
            state,
            agent="execution",
            event="execution_planned",
            summary=f"生成 {len(tasks)} 项执行任务 | 置信度 {confidence.score:.0%}",
            detail={"task_count": len(tasks), "recommendation": confidence.recommendation},
        )
    )
    return updates
