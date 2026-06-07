"""Structured context handoff between Forge agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def summarize_handoff_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Compact summary for conversation_history and reports."""
    refs = payload.get("rule_pack_references") or []
    rule_ids = [r.get("rule_id") for r in refs if isinstance(r, dict) and r.get("rule_id")]
    rationale = (payload.get("decision_rationale") or "")[:200]
    return {
        "problem_type": payload.get("problem_type"),
        "recommended_solution_id": payload.get("recommended_solution_id"),
        "rule_pack_count": len(refs),
        "rule_ids": rule_ids[:6],
        "root_cause_count": len(payload.get("root_causes") or []),
        "decision_rationale": rationale or None,
    }


def build_handoff(
    state: dict[str, Any],
    *,
    from_agent: str,
    to_agent: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Attach structured payload for the next agent in the pipeline.

    Stored under ``agent_context[to_agent]`` with metadata about the sender.
    Also appends a ``handoff`` event to ``conversation_history`` for CLI trace.
    """
    from forge.utils.conversation import record_handoff

    ctx = dict(state.get("agent_context") or {})
    ctx[to_agent] = {
        "from": from_agent,
        "payload": payload,
        "timestamp": _utc_now(),
    }
    updates: dict[str, Any] = {"agent_context": ctx}
    handoff_summary = summarize_handoff_payload(payload)
    updates.update(
        record_handoff(
            state,
            from_agent=from_agent,
            to_agent=to_agent,
            payload_keys=list(payload.keys()),
            handoff_summary=handoff_summary,
        )
    )
    return updates


def get_handoff_payload(state: dict[str, Any], agent: str) -> dict[str, Any]:
    """Return the payload another agent left for ``agent``, or empty dict."""
    entry = (state.get("agent_context") or {}).get(agent) or {}
    payload = entry.get("payload")
    return payload if isinstance(payload, dict) else {}


def merge_agent_context(
    state: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Shallow-merge keys into agent_context (e.g. shared pipeline metadata)."""
    ctx = dict(state.get("agent_context") or {})
    ctx.update(updates)
    return {"agent_context": ctx}
