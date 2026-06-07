"""Rule Pack reference relevance scoring and provenance metrics (ProblemSolver A1)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from forge.agents.rule_pack_refs import classify_reference_source
from forge.agents.solution_output import RulePackReference

_SOURCE_BASE: dict[str, float] = {
    "research": 0.88,
    "keyword": 0.78,
    "scored": 0.72,
    "llm": 0.82,
    "minimum_pad": 0.38,
}


def score_rule_pack_reference(ref: RulePackReference, problem_text: str) -> float:
    """Heuristic relevance in [0, 1] — higher means more pertinent to the question."""
    source = ref.reference_source or classify_reference_source(ref)
    score = _SOURCE_BASE.get(source, 0.55)
    lower = (problem_text or "").lower()
    rid = ref.rule_id.lower()

    if rid in lower:
        score += 0.08
    if ref.title and ref.title in problem_text:
        score += 0.06

    rel = ref.relevance or ""
    if ref.rule_id in rel and len(rel) >= 40:
        score += 0.05
    if "关键词" in rel or "默认引用" in rel or "类型默认" in rel:
        score -= 0.12

    return round(min(1.0, max(0.0, score)), 2)


def apply_relevance_scores(
    refs: list[RulePackReference],
    problem_text: str,
) -> list[RulePackReference]:
    """Attach relevance_score and sort descending (in-place on copies)."""
    scored: list[RulePackReference] = []
    for ref in refs:
        updated = ref.model_copy(
            update={"relevance_score": score_rule_pack_reference(ref, problem_text)}
        )
        scored.append(updated)
    scored.sort(key=lambda r: (-r.relevance_score, r.rule_id))
    return scored


def summarize_reference_provenance(refs: list[RulePackReference]) -> dict[str, Any]:
    """Aggregate provenance for logging and acceptance metrics."""
    if not refs:
        return {
            "total": 0,
            "by_source": {},
            "minimum_pad_ratio": 0.0,
            "high_relevance_ratio": 0.0,
            "avg_relevance_score": 0.0,
        }
    by_source = Counter(classify_reference_source(r) for r in refs)
    pad = by_source.get("minimum_pad", 0)
    high = sum(1 for r in refs if r.relevance_score >= 0.7)
    avg = sum(r.relevance_score for r in refs) / len(refs)
    return {
        "total": len(refs),
        "by_source": dict(by_source),
        "minimum_pad_ratio": round(pad / len(refs), 3),
        "high_relevance_ratio": round(high / len(refs), 3),
        "avg_relevance_score": round(avg, 3),
    }
