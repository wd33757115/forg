"""Tests for compliance check_mode resolution."""

from __future__ import annotations

from forge.core.state import DEFAULT_CHECK_MODE, create_initial_state
from forge.tools.compliance_tools import build_compliance_output_from_checks, run_all_compliance_checks
from forge.utils.check_mode import (
    apply_check_mode_to_compliance_status,
    compute_compliance_verdict,
    resolve_check_mode,
)


def test_resolve_check_mode_from_state():
    state = create_initial_state("check-mode-test")
    state["check_mode"] = "strict"
    assert resolve_check_mode(state) == "strict"


def test_resolve_check_mode_default():
    state = create_initial_state("check-mode-default")
    assert resolve_check_mode(state) == DEFAULT_CHECK_MODE


def test_apply_strict_downgrades_partial():
    assert apply_check_mode_to_compliance_status("partial", "strict") == "non_compliant"


def test_apply_lenient_upgrades_non_compliant():
    assert apply_check_mode_to_compliance_status("non_compliant", "lenient") == "partial"


def test_apply_advisory_unchanged():
    assert apply_check_mode_to_compliance_status("partial", "advisory") == "partial"


def test_compute_strict_treats_warnings_as_non_compliant():
    status, risk, comp = compute_compliance_verdict(
        fail_total=0, warn_total=2, critical_fails=0, check_mode="strict"
    )
    assert comp == "non_compliant"
    assert status == "gaps_found"


def test_compute_lenient_allows_low_gap_partial():
    status, risk, comp = compute_compliance_verdict(
        fail_total=2, warn_total=0, critical_fails=0, check_mode="lenient"
    )
    assert comp == "partial"
    assert risk in ("low", "medium")


def test_build_output_strict_mode():
    state = create_initial_state("check-mode-strict")
    raw = run_all_compliance_checks(state)
    advisory = build_compliance_output_from_checks(raw, check_mode="advisory")
    strict = build_compliance_output_from_checks(raw, check_mode="strict")
    if advisory["compliance_status"] == "partial":
        assert strict["compliance_status"] == "non_compliant"
