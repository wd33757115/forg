"""Tests for ConfidenceScorer."""

from __future__ import annotations

from forge.core.confidence import ConfidenceScorer
from forge.core.confidence.factors import (
    compliance_factor_from_result,
    history_factor_from_knowledge,
)


def test_compliant_high_score():
    state = {
        "last_compliance_result": {
            "compliance_status": "compliant",
            "evidence_coverage": 0.9,
            "results": [{"items": [{"rule_id": "db-001"}]}],
        },
        "last_solution": {
            "rule_pack_references": [{}, {}, {}],
            "problem_type": "security",
        },
        "compliance_retry_count": 0,
        "agent_errors": [],
        "check_mode": "advisory",
    }
    result = ConfidenceScorer().score(state)
    assert result.score >= 0.75
    assert result.level == "high"
    assert result.recommendation == "auto_execute"


def test_partial_with_retry_medium():
    state = {
        "last_compliance_result": {"compliance_status": "partial"},
        "last_solution": {"rule_pack_references": [{}]},
        "compliance_retry_count": 1,
        "agent_errors": [],
        "check_mode": "advisory",
    }
    result = ConfidenceScorer().score(state)
    assert 0.45 <= result.score < 0.75
    assert result.recommendation == "needs_review"


def test_non_compliant_strict_block():
    state = {
        "last_compliance_result": {"compliance_status": "non_compliant"},
        "last_solution": {},
        "compliance_retry_count": 2,
        "agent_errors": [{"agent": "x"}, {"agent": "y"}],
        "check_mode": "strict",
    }
    result = ConfidenceScorer().score(state)
    assert result.score < 0.45
    assert result.recommendation == "block"


def test_history_factor_from_outcomes():
    state = {
        "problem_type": "security",
        "knowledge_base": [
            {"tags": ["security"], "outcome": "success"},
            {"tags": ["security"], "outcome": "failed"},
        ],
    }
    assert history_factor_from_knowledge(state) == 0.5


def test_compliance_factor_strict_lower():
    base = compliance_factor_from_result({"compliance_status": "partial"}, check_mode="advisory")
    strict = compliance_factor_from_result({"compliance_status": "partial"}, check_mode="strict")
    assert strict < base
