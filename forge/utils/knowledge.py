"""Project knowledge_base helpers — structured append and tag-based search (v1.0)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from forge.core.state import ProjectState


def append_knowledge(
    state: ProjectState,
    *,
    agent: str,
    summary: str,
    tags: list[str] | None = None,
    category: str = "general",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a knowledge_base entry dict (caller merges into state updates)."""
    kb = state.get("knowledge_base", [])
    entry = {
        "id": f"kb-{state.get('project_id', 'unknown')}-{agent}-{len(kb)}",
        "category": category,
        "content": summary,
        "source": agent,
        "tags": tags or [],
        "metadata": detail or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return entry


def search_knowledge(
    state: ProjectState,
    *,
    tags: list[str] | None = None,
    agent: str | None = None,
    category: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Filter knowledge_base entries by tag/agent/category (case-insensitive tag match).

    Returns most recent matches first.
    """
    entries = list(state.get("knowledge_base", []))
    if not entries:
        return []

    tag_set = {t.lower() for t in (tags or [])}
    results: list[dict[str, Any]] = []

    for entry in reversed(entries):
        if agent and entry.get("source") != agent:
            continue
        if category and entry.get("category") != category:
            continue
        if tag_set:
            entry_tags = {str(t).lower() for t in entry.get("tags", [])}
            if not tag_set.intersection(entry_tags):
                continue
        results.append(entry)
        if len(results) >= limit:
            break

    return results


def format_knowledge_context(entries: list[dict[str, Any]]) -> str:
    """Format prior cases for injection into agent prompts."""
    if not entries:
        return "（无相关历史案例）"
    lines = ["## 相关历史案例（knowledge_base）"]
    for entry in entries:
        tags = ", ".join(entry.get("tags", []))
        lines.append(f"- [{entry.get('source', '?')}] ({tags}) {entry.get('content', '')[:200]}")
    return "\n".join(lines)
