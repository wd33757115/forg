"""Conversation history helpers — track Agent interactions in ProjectState."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def record_conversation(
    state: dict[str, Any],
    *,
    agent: str,
    event: str,
    summary: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Append an interaction record to conversation_history.

    Returns a state update dict for LangGraph nodes.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "event": event,
        "summary": summary,
        "detail": detail or {},
    }
    history = list(state.get("conversation_history", []))
    history.append(entry)
    return {"conversation_history": history}


def record_thinking(
    state: dict[str, Any],
    *,
    agent: str,
    thought: str,
    decision: str | None = None,
    evidence: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Record a thinking-chain step — key decisions and rationale for an agent.

    Appears in ``conversation_history`` with ``event=thinking`` for CLI/API trace.
    """
    detail: dict[str, Any] = dict(extra or {})
    if decision:
        detail["decision"] = decision
    if evidence:
        detail["evidence"] = evidence
    return record_conversation(
        state,
        agent=agent,
        event="thinking",
        summary=thought,
        detail=detail,
    )


def record_handoff(
    state: dict[str, Any],
    *,
    from_agent: str,
    to_agent: str,
    payload_keys: list[str] | None = None,
    handoff_summary: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Record structured handoff between agents in conversation_history."""
    summary = handoff_summary or {}
    short = summary.get("recommended_solution_id") or summary.get("problem_type") or ""
    summary_line = f"传递上下文给 {to_agent}"
    if short:
        summary_line += f" ({short})"
    detail: dict[str, Any] = {
        "from_agent": from_agent,
        "to_agent": to_agent,
        "payload_keys": payload_keys or [],
    }
    if handoff_summary:
        detail["handoff_summary"] = handoff_summary
    return record_conversation(
        state,
        agent=from_agent,
        event="handoff",
        summary=summary_line,
        detail=detail,
    )
