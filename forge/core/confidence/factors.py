"""Pure factor calculators for confidence scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_RULE_ID_PREFIXES = ("db-", "itil-", "si-")


def _dict_rule_id_mapping_rate(compliance: dict[str, Any]) -> float:
    items: list[dict[str, Any]] = []
    for mod in compliance.get("results") or []:
        items.extend(mod.get("items") or [])
    if not items:
        return 0.0
    mapped = 0
    for item in items:
        rid = str(item.get("rule_id") or item.get("check_id") or "")
        if any(rid.startswith(p) for p in _RULE_ID_PREFIXES):
            mapped += 1
    return mapped / len(items)


@dataclass
class ConfidenceFactors:
    compliance_factor: float
    evidence_factor: float
    retry_penalty: float
    error_penalty: float
    history_factor: float


_STATUS_SCORES = {
    "compliant": 1.0,
    "pass": 1.0,
    "partial": 0.6,
    "gaps_found": 0.55,
    "non_compliant": 0.2,
    "fail": 0.2,
}


def compliance_factor_from_result(
    compliance: dict[str, Any] | None,
    *,
    check_mode: str = "advisory",
) -> float:
    if not compliance:
        return 0.3
    status = compliance.get("compliance_status") or compliance.get("overall_status") or ""
    base = _STATUS_SCORES.get(str(status).lower(), 0.4)
    if check_mode == "strict":
        base *= 0.90
    elif check_mode == "lenient" and base < 0.6:
        base = min(0.6, base + 0.1)
    return round(min(1.0, max(0.0, base)), 3)


def evidence_factor_from_state(state: dict[str, Any]) -> float:
    solution = state.get("last_solution") or {}
    compliance = state.get("last_compliance_result") or {}
    refs = solution.get("rule_pack_references") or []
    ref_score = min(1.0, len(refs) / 5.0)
    mapping = _dict_rule_id_mapping_rate(compliance) if compliance else 0.0
    coverage = float(compliance.get("evidence_coverage", 0) or 0)
    if coverage <= 0 and compliance.get("results"):
        covered = sum(1 for r in compliance["results"] if r.get("rule_id"))
        coverage = covered / max(1, len(compliance["results"]))
    combined = 0.55 * ref_score + 0.25 * mapping + 0.20 * min(1.0, coverage)
    return round(min(1.0, max(0.0, combined)), 3)


def retry_penalty_from_count(retry_count: int, *, per_event: float = 0.12, cap: float = 0.36) -> float:
    return round(min(cap, max(0, retry_count) * per_event), 3)


def error_penalty_from_state(
    state: dict[str, Any],
    *,
    per_event: float = 0.08,
    cap: float = 0.24,
) -> float:
    errors = len(state.get("agent_errors") or [])
    degraded = len(state.get("degraded_agents") or [])
    return round(min(cap, (errors + degraded) * per_event), 3)


def history_factor_from_knowledge(
    state: dict[str, Any],
    *,
    problem_type: str | None = None,
) -> float:
    """Success rate from knowledge_base entries with outcome (phase 4)."""
    ptype = problem_type or state.get("problem_type") or (state.get("last_solution") or {}).get("problem_type")
    entries = state.get("knowledge_base") or []
    if not ptype or not entries:
        return 0.5
    relevant = [
        e
        for e in entries
        if ptype in (e.get("tags") or []) or e.get("metadata", {}).get("problem_type") == ptype
    ]
    with_outcome = [e for e in relevant if e.get("outcome")]
    if not with_outcome:
        return 0.5
    successes = sum(1 for e in with_outcome if e.get("outcome") in ("success", "compliant", "resolved"))
    return round(successes / len(with_outcome), 3)


def compute_factors(state: dict[str, Any]) -> ConfidenceFactors:
    check_mode = state.get("check_mode") or "advisory"
    compliance = state.get("last_compliance_result") or {}
    return ConfidenceFactors(
        compliance_factor=compliance_factor_from_result(compliance, check_mode=check_mode),
        evidence_factor=evidence_factor_from_state(state),
        retry_penalty=retry_penalty_from_count(int(state.get("compliance_retry_count") or 0)),
        error_penalty=error_penalty_from_state(state),
        history_factor=history_factor_from_knowledge(state),
    )
