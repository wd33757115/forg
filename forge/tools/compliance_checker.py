"""Multi-standard compliance scanning tools."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from forge.core.rule_pack import RulePack
from forge.core.state import ProjectState


class ComplianceScanResult(BaseModel):
    overall_status: str
    findings: list[str] = Field(default_factory=list)
    checked_at: str = ""


def run_compliance_scan(state: ProjectState, packs: dict[str, RulePack]) -> ComplianceScanResult:
    """
    Scan project state against enabled Rule Packs.

    Phase 1 uses lightweight heuristics. Phase 2 will map evidence artifacts
    to specific rule clauses and compute coverage scores.
    """
    findings: list[str] = []
    documents = state.get("documents", [])
    wbs = state.get("wbs", {})
    doc_titles = {d.get("title", "").lower() for d in documents}

    for module_id, pack in packs.items():
        for rule in pack.rules:
            gap = _check_rule(rule.id, rule.checks, doc_titles, wbs)
            if gap:
                findings.append(f"[{module_id}/{rule.id}] {rule.title}: {gap}")

    status = "pass" if not findings else "gaps_found"
    return ComplianceScanResult(
        overall_status=status,
        findings=findings,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


def _check_rule(
    rule_id: str,
    checks: list[str],
    doc_titles: set[str],
    wbs: dict,
) -> str | None:
    """Return gap description if a rule check fails, else None."""
    for check in checks:
        check_lower = check.lower()
        if check_lower.startswith("document:"):
            required = check_lower.replace("document:", "").strip()
            if not any(required in t for t in doc_titles):
                return f"Missing document containing '{required}'"
        if check_lower.startswith("wbs:"):
            required = check_lower.replace("wbs:", "").strip()
            if required not in wbs:
                return f"WBS item '{required}' not defined"
    return None
