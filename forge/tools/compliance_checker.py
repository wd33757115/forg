"""Legacy compliance scan wrapper — delegates to compliance_tools."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from forge.core.rule_pack import RuleModule
from forge.core.state import ProjectState
from forge.tools.compliance_tools import build_compliance_output_from_checks, run_all_compliance_checks


class ComplianceScanResult(BaseModel):
    overall_status: str
    findings: list[str] = Field(default_factory=list)
    checked_at: str = ""


def run_compliance_scan(state: ProjectState, packs: dict[str, RuleModule]) -> ComplianceScanResult:
    """
    Scan project state against enabled Rule Packs.

    Delegates to compliance_tools; kept for backward compatibility.
    """
    _ = packs  # modules resolved from state.enabled_modules
    raw = run_all_compliance_checks(state)
    payload = build_compliance_output_from_checks(raw)
    return ComplianceScanResult(
        overall_status=payload["overall_status"],
        findings=payload["missing_items"],
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
