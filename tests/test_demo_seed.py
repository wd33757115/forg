"""Tests for demo evidence pre-seeding."""

from __future__ import annotations

from forge.cli.demo_seed import apply_demo_evidence_seed
from forge.core.state import create_initial_state
from forge.tools.compliance_tools import build_compliance_output_from_checks, run_all_compliance_checks


def test_apply_demo_seed_adds_documents_and_wbs():
    state = create_initial_state("seed-test")
    seeded = apply_demo_evidence_seed(state)
    assert len(seeded["documents"]) >= 5
    assert "requirements" in seeded["wbs"]
    assert "acceptance" in seeded["wbs"]


def test_apply_demo_seed_idempotent():
    state = create_initial_state("seed-idempotent")
    state["documents"] = [{"title": "已有文档", "doc_type": "方案"}]
    seeded = apply_demo_evidence_seed(state)
    assert len(seeded["documents"]) == 1


def test_demo_seed_improves_compliance_to_partial_or_better():
    state = create_initial_state("seed-cmp")
    state["rule_pack"] = {"protection_level": "3"}
    raw_before = run_all_compliance_checks(state)
    fails_before = sum(
        1 for m in raw_before["modules"].values() for i in m["items"] if i["status"] == "fail"
    )

    seeded = apply_demo_evidence_seed(state)
    raw_after = run_all_compliance_checks(seeded)
    fails_after = sum(
        1 for m in raw_after["modules"].values() for i in m["items"] if i["status"] == "fail"
    )
    after = build_compliance_output_from_checks(raw_after, check_mode="advisory")

    assert fails_after < fails_before
    assert after["compliance_status"] in ("compliant", "partial")
