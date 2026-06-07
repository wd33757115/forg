"""Pluggable execution backends — simulate (default), local manifest, webhook."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib import error, request

from forge.config import get_settings
from forge.core.execution.models import ExecutionResult
from forge.core.execution.simulate import simulate_execution
from forge.core.state import ProjectState

ExecutionMode = Literal["simulate", "local_manifest", "webhook"]


def resolve_execution_mode(state: ProjectState | dict[str, Any]) -> ExecutionMode:
    """State override wins, then ``FORGE_EXECUTION_MODE`` from settings."""
    raw = state.get("execution_mode") or get_settings().execution_mode
    if raw in ("simulate", "local_manifest", "webhook"):
        return raw  # type: ignore[return-value]
    return "simulate"


def run_task_execution(
    tasks: list[dict[str, Any]],
    state: ProjectState | dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Execute ready tasks via configured backend."""
    mode = resolve_execution_mode(state)
    if mode == "local_manifest":
        return execute_local_manifest(tasks, state)
    if mode == "webhook":
        return execute_webhook(tasks, state)
    return simulate_execution(tasks)


def execute_local_manifest(
    tasks: list[dict[str, Any]],
    state: ProjectState | dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Write ready tasks to ``reports/execution/`` as JSON manifest (external runner can consume).

    Marks tasks ``executed`` with manifest path in result metadata.
    """
    settings = get_settings()
    out_dir = Path(settings.execution_manifest_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = state.get("run_id", "run")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest_path = out_dir / f"exec_{run_id}_{stamp}.json"

    ready = [dict(t) for t in tasks if t.get("status") == "ready"]
    payload = {
        "run_id": run_id,
        "project_id": state.get("project_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tasks": ready,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    updated: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for raw in tasks:
        task = dict(raw)
        if task.get("status") == "ready":
            task["status"] = "executed"
            result = ExecutionResult(
                task_id=task["id"],
                status="success",
                summary=f"执行清单已写入: {manifest_path.name}",
                metadata={
                    "backend": "local_manifest",
                    "manifest_path": str(manifest_path),
                    "task_type": task.get("task_type"),
                },
            )
            results.append(result.to_state_dict())
        updated.append(task)
    return updated, results


def execute_webhook(
    tasks: list[dict[str, Any]],
    state: ProjectState | dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """POST ready tasks to ``FORGE_EXECUTION_WEBHOOK_URL``; fall back to simulate if unset."""
    url = get_settings().execution_webhook_url
    if not url:
        updated, results = simulate_execution(tasks)
        for r in results:
            r.setdefault("metadata", {})
            r["metadata"]["backend"] = "webhook_fallback_simulate"
            r["metadata"]["reason"] = "FORGE_EXECUTION_WEBHOOK_URL not set"
        return updated, results

    ready = [dict(t) for t in tasks if t.get("status") == "ready"]
    body = json.dumps(
        {
            "run_id": state.get("run_id"),
            "project_id": state.get("project_id"),
            "tasks": ready,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=get_settings().execution_webhook_timeout) as resp:
            ok = 200 <= resp.status < 300
    except (error.URLError, TimeoutError, OSError):
        ok = False

    updated: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for raw in tasks:
        task = dict(raw)
        if task.get("status") != "ready":
            updated.append(task)
            continue
        task["status"] = "executed" if ok else "failed"
        result = ExecutionResult(
            task_id=task["id"],
            status="success" if ok else "failed",
            summary=f"Webhook {'成功' if ok else '失败'}: {task.get('title', '')[:60]}",
            metadata={"backend": "webhook", "url": url},
        )
        results.append(result.to_state_dict())
        updated.append(task)
    return updated, results
