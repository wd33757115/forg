"""Simulated execution of ready tasks (in-memory, no external systems)."""

from __future__ import annotations

from forge.core.execution.models import ExecutionResult, ExecutionTask


def simulate_execution(tasks: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Mark ``ready`` tasks as ``executed`` and produce ExecutionResult records.

    Returns (updated_tasks, execution_results).
    """
    updated: list[dict] = []
    results: list[dict] = []
    for raw in tasks:
        task = dict(raw)
        if task.get("status") == "ready":
            task["status"] = "executed"
            result = ExecutionResult(
                task_id=task["id"],
                status="success",
                summary=f"模拟执行完成: {task.get('title', '')[:80]}",
                metadata={"simulated": True, "task_type": task.get("task_type")},
            )
            results.append(result.to_state_dict())
        updated.append(task)
    return updated, results
