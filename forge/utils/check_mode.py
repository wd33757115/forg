"""Compliance check_mode resolution and verdict logic (v1.0)."""

from __future__ import annotations

from forge.config import get_settings
from forge.core.state import ComplianceCheckMode, DEFAULT_CHECK_MODE, ProjectState

_VALID: tuple[ComplianceCheckMode, ...] = ("strict", "advisory", "lenient")


def resolve_check_mode(state: ProjectState) -> ComplianceCheckMode:
    """Read check_mode from session state, else from settings, else default."""
    raw = state.get("check_mode")
    if raw in _VALID:
        return raw  # type: ignore[return-value]
    settings_mode = get_settings().compliance_check_mode
    if settings_mode in _VALID:
        return settings_mode
    return DEFAULT_CHECK_MODE


def compute_compliance_verdict(
    *,
    fail_total: int,
    warn_total: int,
    critical_fails: int,
    check_mode: ComplianceCheckMode = "advisory",
) -> tuple[str, str, str]:
    """
    Derive overall_status, risk_level, compliance_status from check counts.

    Modes (IMPLEMENTATION_PLAN §4.5):
    - strict: any fail or warning → non_compliant
    - advisory: gaps → partial when risk is manageable; high/critical may block
    - lenient: only high-risk gaps block; low/medium → partial
    """
    if check_mode == "strict":
        gap_total = fail_total + warn_total
        if gap_total == 0:
            return "pass", "low", "compliant"
        if critical_fails >= 2 or fail_total >= 6:
            return "critical", "critical", "non_compliant"
        risk = "high" if fail_total >= 3 else "medium"
        if warn_total and fail_total == 0:
            risk = "low"
        return "gaps_found", risk, "non_compliant"

    if check_mode == "lenient":
        if fail_total == 0 and warn_total == 0:
            return "pass", "low", "compliant"
        blocking = critical_fails >= 2 or fail_total >= 6 or (
            critical_fails >= 1 and fail_total >= 3
        )
        if blocking:
            risk = "critical" if critical_fails >= 2 or fail_total >= 6 else "high"
            status = "critical" if risk == "critical" else "gaps_found"
            return status, risk, "non_compliant"
        risk = "medium" if fail_total >= 2 else "low"
        return "gaps_found", risk, "partial"

    # advisory (default)
    if critical_fails >= 2 or fail_total >= 6:
        return "critical", "critical", "non_compliant"
    if fail_total > 0:
        risk_level = "high" if fail_total >= 3 else "medium"
        compliance_status = "partial" if risk_level in ("low", "medium") else "non_compliant"
        return "gaps_found", risk_level, compliance_status
    if warn_total > 0:
        return "gaps_found", "low", "partial"
    return "pass", "low", "compliant"


def apply_check_mode_to_compliance_status(
    base_status: str,
    check_mode: ComplianceCheckMode,
) -> str:
    """
    Adjust compliant | partial | non_compliant when verdict comes from LLM path.

  For heuristic paths, prefer ``compute_compliance_verdict`` at check time.
    """
    if check_mode == "strict" and base_status in ("partial", "compliant"):
        if base_status == "partial":
            return "non_compliant"
    if check_mode == "lenient" and base_status == "non_compliant":
        return "partial"
    return base_status
