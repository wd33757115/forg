"""Run statistics helpers for CLI demo output."""

from __future__ import annotations

from typing import Any


def compute_confidence_score(result: dict[str, Any]) -> float:
    """
    Heuristic confidence 0.0–1.0 from compliance outcome, retries, and Rule Pack refs.

    Used for v1.1 ProjectState.confidence_score (set at finalize).
    """
    score = 0.65
    compliance = result.get("last_compliance_result") or {}
    status = compliance.get("compliance_status", compliance.get("overall_status", ""))
    if status == "compliant":
        score += 0.2
    elif status == "partial":
        score += 0.08
    elif status == "non_compliant":
        score -= 0.1

    retries = int(result.get("compliance_retry_count") or 0)
    score -= min(0.25, retries * 0.12)

    solution = result.get("last_solution") or {}
    refs = len(solution.get("rule_pack_references") or [])
    score += min(0.12, refs * 0.03)

    errors = len(result.get("agent_errors") or [])
    score -= min(0.2, errors * 0.08)

    return round(max(0.0, min(1.0, score)), 2)


def compute_run_stats(result: dict[str, Any], *, elapsed_ms: float | None = None) -> dict[str, Any]:
    """Aggregate pipeline stats for demo footer."""
    history = result.get("conversation_history") or []
    trace = result.get("pipeline_trace") or []

    thinking_steps = sum(1 for h in history if h.get("event") == "thinking")
    retry_events = [h for h in history if h.get("event") == "compliance_retry"]
    handoffs = [h for h in history if h.get("event") == "handoff"]
    compliance_checks = [h for h in history if h.get("event") == "compliance_check"]

    agents_run = {e.get("agent") for e in trace if e.get("agent")}
    success_count = sum(1 for e in trace if e.get("status") == "success")
    failed_count = sum(1 for e in trace if e.get("status") == "failed")

    compliance = result.get("last_compliance_result") or {}
    docs = result.get("generated_documents") or []

    return {
        "elapsed_ms": elapsed_ms,
        "elapsed_s": round(elapsed_ms / 1000, 2) if elapsed_ms else None,
        "pipeline_steps": len(trace),
        "agents_invoked": len(agents_run),
        "agents_success": success_count,
        "agents_failed": failed_count,
        "thinking_steps": thinking_steps,
        "compliance_retries": int(result.get("compliance_retry_count") or 0),
        "compliance_retry_events": len(retry_events),
        "compliance_checks": len(compliance_checks),
        "handoffs": len(handoffs),
        "documents_generated": len(docs),
        "compliance_status": compliance.get("compliance_status", "unknown"),
        "risk_level": compliance.get("risk_level") or result.get("risk_level", "unknown"),
        "confidence_score": result.get("confidence_score") or compute_confidence_score(result),
        "problem_type": result.get("problem_type")
        or (result.get("last_solution") or {}).get("problem_type", "—"),
    }
