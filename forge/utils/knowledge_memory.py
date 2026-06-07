"""Knowledge + memory graph helpers — closed-loop case retrieval for agents."""

from __future__ import annotations

import re
from typing import Any

from forge.core.memory.graph import MemoryGraph
from forge.core.state import ProjectState
from forge.utils.knowledge import search_knowledge

_RULE_ID_PATTERN = re.compile(r"\b(?:db|itil|si)-[a-z0-9-]+\b", re.IGNORECASE)


def extract_rule_ids_from_text(text: str) -> list[str]:
    """Pull canonical rule_id tokens from free text."""
    return list(dict.fromkeys(m.group(0).lower() for m in _RULE_ID_PATTERN.finditer(text or "")))


def rebuild_memory_graph(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build full memory graph snapshot from knowledge_base entries."""
    return MemoryGraph.from_knowledge_entries(entries).to_dict()


def _graph_boosted_entry_ids(
    graph: dict[str, Any] | None,
    rule_ids: list[str],
) -> set[str]:
    """Entry node ids linked to given rule_ids in memory_graph."""
    if not graph or not rule_ids:
        return set()
    rule_set = set(rule_ids)
    rule_node_ids = {
        n["id"]
        for n in graph.get("nodes", [])
        if n.get("node_type") == "rule" and n.get("label") in rule_set
    }
    if not rule_node_ids:
        return set()
    boosted: set[str] = set()
    for edge in graph.get("edges", []):
        if edge.get("relation") == "references" and edge.get("target_id") in rule_node_ids:
            boosted.add(edge.get("source_id", ""))
    return {b for b in boosted if b}


def _keyword_hit_score(entry: dict[str, Any], keywords: list[str], problem_text: str) -> float:
    """Weighted keyword overlap between case and current problem."""
    blob = " ".join(
        [
            str(entry.get("content", "")),
            " ".join(entry.get("tags") or []),
            str((entry.get("metadata") or {})),
        ]
    ).lower()
    lower = problem_text.lower()
    score = 0.0
    for kw in keywords:
        kl = kw.lower()
        if kl in blob:
            score += 1.5
        if kl in lower and kl in blob:
            score += 0.5
    return score


def search_similar_cases(
    state: ProjectState | dict[str, Any],
    *,
    problem_type: str,
    problem_text: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """
    Rank prior cases by tag/keyword match and memory_graph rule linkage.

    Used by ProblemSolver before ReAct to inject institutional memory.
    Each result may include ``match_reason`` and ``match_score`` (A5).
    """
    keywords = [w for w in problem_text.replace("，", " ").split() if len(w) >= 2][:8]
    rule_ids = extract_rule_ids_from_text(problem_text)
    tag_candidates = [problem_type]
    if problem_type == "service_management":
        tag_candidates.append("itil")
    base = search_knowledge(
        state,
        tags=tag_candidates,
        keywords=keywords or None,
        limit=limit * 3,
    )
    boosted_ids = _graph_boosted_entry_ids(state.get("memory_graph"), rule_ids)
    scored: list[tuple[float, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for entry in base:
        eid = str(entry.get("id", id(entry)))
        if eid in seen:
            continue
        seen.add(eid)
        score = 1.0
        reasons: list[str] = ["tag"]
        if eid in boosted_ids:
            score += 2.0
            reasons.append("memory_graph")
        entry_rules = set(entry.get("related_rules") or [])
        overlap = rule_ids and entry_rules.intersection(rule_ids)
        if overlap:
            score += 1.5
            reasons.append(f"rule:{','.join(sorted(overlap)[:2])}")
        kw_score = _keyword_hit_score(entry, keywords, problem_text)
        if kw_score > 0:
            score += kw_score
            reasons.append("keyword")
        if entry.get("outcome") in ("success", "compliant", "resolved"):
            score += 0.5
            reasons.append("positive_outcome")
        enriched = dict(entry)
        enriched["match_score"] = round(score, 2)
        enriched["match_reason"] = "+".join(reasons)
        scored.append((score, enriched.get("match_reason", ""), enriched))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, _, e in scored[:limit]]


def format_memory_context(entries: list[dict[str, Any]]) -> str:
    """Format prior cases with outcome and related_rules for prompt injection."""
    if not entries:
        return "（无相关历史案例）"
    lines = ["## 相关历史案例（knowledge_base + memory_graph）"]
    for entry in entries:
        tags = ", ".join(entry.get("tags", []))
        outcome = entry.get("outcome") or "—"
        rules = ", ".join(entry.get("related_rules") or [])[:80]
        rules_part = f" | rules: {rules}" if rules else ""
        match = entry.get("match_reason")
        match_part = f" | match={match}" if match else ""
        lines.append(
            f"- [{entry.get('source', '?')}] outcome={outcome} ({tags}) "
            f"{entry.get('content', '')[:180]}{rules_part}{match_part}"
        )
    return "\n".join(lines)
