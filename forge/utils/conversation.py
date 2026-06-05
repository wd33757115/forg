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
