"""Quality metrics for v1.0 acceptance (reference rate, rule_id mapping)."""

from __future__ import annotations

from forge.agents.compliance_output import CheckItem, ComplianceOutput

_RULE_ID_PREFIXES = ("db-", "itil-", "si-")


def _is_canonical_rule_id(value: str) -> bool:
    v = (value or "").strip()
    return any(v.startswith(p) for p in _RULE_ID_PREFIXES)


def check_item_rule_id(item: CheckItem) -> str:
    """Resolve canonical rule_id from CheckItem fields."""
    if item.rule_id and _is_canonical_rule_id(item.rule_id):
        return item.rule_id
    if _is_canonical_rule_id(item.check_id):
        return item.check_id
    ref = (item.rule_reference or "").split(",")[0].strip()
    if _is_canonical_rule_id(ref):
        return ref
    return ""


def compliance_rule_id_mapping_rate(output: ComplianceOutput) -> float:
    """Fraction of check items with a canonical rule_id (target ≥ 80%)."""
    items = [item for mod in output.results for item in mod.items]
    if not items:
        return 0.0
    mapped = sum(1 for item in items if check_item_rule_id(item))
    return mapped / len(items)


def solution_has_rule_references(solution: dict | None) -> bool:
    """True when last_solution contains at least one rule_pack_reference."""
    if not solution:
        return False
    refs = solution.get("rule_pack_references") or []
    return len(refs) > 0


def solution_reference_coverage(results: list[dict | None]) -> float:
    """Fraction of runs whose solution includes rule_pack_references (target ≥ 70%)."""
    if not results:
        return 0.0
    hits = sum(1 for s in results if solution_has_rule_references(s))
    return hits / len(results)


def solution_high_relevance_rate(solution: dict | None, *, threshold: float = 0.7) -> float:
    """Fraction of refs with relevance_score >= threshold (A1 acceptance)."""
    if not solution:
        return 0.0
    refs = solution.get("rule_pack_references") or []
    if not refs:
        return 0.0
    high = sum(1 for r in refs if float(r.get("relevance_score") or 0) >= threshold)
    return high / len(refs)
