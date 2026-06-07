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
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a knowledge_base entry dict (caller merges into state updates).

    Pass a pre-built ``item`` dict to store as-is (must include id/content).
    """
    if item is not None:
        entry = dict(item)
        entry.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        return entry
    kb = state.get("knowledge_base", [])
    related_rules = (detail or {}).pop("related_rules", None) if detail else None
    outcome = (detail or {}).pop("outcome", None) if detail else None
    entry_type = (detail or {}).pop("type", "case") if detail else "case"
    entry = {
        "id": f"kb-{state.get('project_id', 'unknown')}-{agent}-{len(kb)}",
        "category": category,
        "content": summary,
        "source": agent,
        "tags": tags or [],
        "type": entry_type,
        "related_rules": related_rules or [],
        "outcome": outcome,
        "metadata": detail or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return entry


def append_knowledge_to_state(
    state: ProjectState,
    entry: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Return state update with one new knowledge_base entry appended."""
    kb = list(state.get("knowledge_base", []))
    kb.append(entry)
    return {"knowledge_base": kb}


def _keyword_overlap(text: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in lower)
    return hits / len(keywords)


def _score_entry(
    entry: dict[str, Any],
    tag_set: set[str],
    agent: str | None,
    *,
    keywords: list[str] | None = None,
    match_all_tags: bool = False,
) -> float:
    score = 0.0
    entry_tags = {str(t).lower() for t in entry.get("tags", [])}
    if tag_set:
        overlap = tag_set.intersection(entry_tags)
        if match_all_tags and overlap != tag_set:
            return -1.0
        score += len(overlap) * 2.0
    if agent and entry.get("source") == agent:
        score += 1.0
    if entry.get("outcome") in ("success", "compliant", "resolved"):
        score += 0.5
    if entry.get("related_rules"):
        score += 0.3
    content = f"{entry.get('content', '')} {' '.join(entry.get('tags', []))}"
    kw_score = _keyword_overlap(content, keywords or [])
    score += kw_score * 3.0
    return score


def search_knowledge(
    state: ProjectState,
    *,
    tags: list[str] | None = None,
    agent: str | None = None,
    category: str | None = None,
    keywords: list[str] | None = None,
    match_all_tags: bool = False,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Filter and rank knowledge_base entries by tag/agent/category/keywords.

  - Multiple tags: overlap increases rank; ``match_all_tags=True`` requires every tag.
  - ``keywords``: simple substring match against content + tags (similarity ranking).
    """
    entries = list(state.get("knowledge_base", []))
    if not entries:
        return []

    tag_set = {t.lower() for t in (tags or [])}
    kw_list = [k.strip() for k in (keywords or []) if k.strip()]
    scored: list[tuple[float, dict[str, Any]]] = []

    for entry in entries:
        if agent and entry.get("source") != agent:
            continue
        if category and entry.get("category") != category:
            continue
        if tag_set and not match_all_tags:
            entry_tags = {str(t).lower() for t in entry.get("tags", [])}
            if not tag_set.intersection(entry_tags):
                continue
        rank = _score_entry(
            entry,
            tag_set,
            agent,
            keywords=kw_list,
            match_all_tags=match_all_tags,
        )
        if rank < 0:
            continue
        if kw_list and rank == 0 and not tag_set and not agent:
            continue
        scored.append((rank, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:limit]]


def format_knowledge_context(entries: list[dict[str, Any]]) -> str:
    """Format prior cases for injection into agent prompts."""
    if not entries:
        return "（无相关历史案例）"
    lines = ["## 相关历史案例（knowledge_base）"]
    for entry in entries:
        tags = ", ".join(entry.get("tags", []))
        lines.append(f"- [{entry.get('source', '?')}] ({tags}) {entry.get('content', '')[:200]}")
    return "\n".join(lines)
