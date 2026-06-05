"""Serialize Forge workflow results for API / JSON export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import messages_to_dict


def _agents_contributed(result: dict[str, Any]) -> list[str]:
    agents: list[str] = []
    if result.get("last_solution"):
        agents.append("problem_solver")
    if result.get("last_security_result"):
        agents.append("security")
    if result.get("last_operations_result"):
        agents.append("operations")
    if result.get("last_compliance_result"):
        agents.append("compliance")
    if result.get("generated_documents"):
        agents.append("document")
    if result.get("last_pm_advice"):
        agents.append("pm_advisor")
    return agents


def build_api_response(
    result: dict[str, Any],
    *,
    question: str,
    scenario: str = "",
    elapsed_ms: float | None = None,
) -> dict[str, Any]:
    """
    Build a JSON-safe response dict from a post-workflow ProjectState.

    Strips non-serializable LangChain message objects from the top level while
    preserving agent outputs in ``final_output``.
    """
    final = result.get("final_output") or {}

    payload: dict[str, Any] = {
        "success": len(result.get("agent_errors", [])) == 0,
        "run_id": result.get("run_id") or final.get("run_id"),
        "project_id": result.get("project_id"),
        "question": question,
        "scenario": scenario,
        "agents": _agents_contributed(result),
        "compliance_status": final.get("compliance_status")
        or (result.get("last_compliance_result") or {}).get("compliance_status"),
        "risk_level": final.get("risk_level")
        or (result.get("last_compliance_result") or {}).get("risk_level"),
        "compliance_retry_count": result.get("compliance_retry_count", 0),
        "document_count": len(result.get("generated_documents") or []),
        "solution": final.get("solution") or result.get("last_solution"),
        "compliance": final.get("compliance") or result.get("last_compliance_result"),
        "security": final.get("security") or result.get("last_security_result"),
        "operations": final.get("operations") or result.get("last_operations_result"),
        "documents": final.get("generated_documents") or result.get("generated_documents") or [],
        "pm_advice": final.get("pm_advice") or result.get("last_pm_advice"),
        "workflow_plan": result.get("workflow_plan") or final.get("workflow_plan"),
        "pipeline_trace": result.get("pipeline_trace") or final.get("pipeline_trace") or [],
        "agent_errors": result.get("agent_errors") or final.get("agent_errors") or [],
        "degraded_agents": result.get("degraded_agents") or [],
        "conversation_history": result.get("conversation_history") or [],
        "messages": messages_to_dict(result.get("messages") or []),
        "final_output": final,
    }
    if elapsed_ms is not None:
        payload["elapsed_ms"] = round(elapsed_ms, 1)
        payload["elapsed_seconds"] = round(elapsed_ms / 1000.0, 2)
    return payload


def save_run_result(
    result: dict[str, Any],
    path: str | Path,
    *,
    question: str,
    scenario: str = "",
    elapsed_ms: float | None = None,
) -> Path:
    """Persist full run result as UTF-8 JSON."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_api_response(
        result,
        question=question,
        scenario=scenario,
        elapsed_ms=elapsed_ms,
    )
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def default_run_result_path(run_id: str, project_id: str = "cli-demo") -> Path:
    """Default path: .forge_state/runs/{project_id}_{run_id}.json"""
    return Path(".forge_state") / "runs" / f"{project_id}_{run_id}.json"
