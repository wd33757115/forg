"""Tests for CLI run statistics helpers."""

from __future__ import annotations

from forge.cli.stats import compute_confidence_score, compute_run_stats


def test_compute_confidence_score_partial():
    result = {
        "last_compliance_result": {"compliance_status": "partial"},
        "compliance_retry_count": 0,
        "last_solution": {"rule_pack_references": [{}, {}, {}]},
        "agent_errors": [],
    }
    score = compute_confidence_score(result)
    assert 0.5 <= score <= 1.0


def test_compute_run_stats_counts():
    result = {
        "pipeline_trace": [
            {"agent": "problem_solver", "status": "success"},
            {"agent": "compliance", "status": "success"},
        ],
        "conversation_history": [
            {"event": "thinking", "agent": "problem_solver"},
            {"event": "compliance_retry", "agent": "supervisor", "detail": {"retry_count": 1}},
            {"event": "handoff", "agent": "problem_solver", "detail": {}},
        ],
        "compliance_retry_count": 1,
        "last_compliance_result": {"compliance_status": "partial", "risk_level": "medium"},
        "generated_documents": [{"title": "a"}],
        "problem_type": "security",
    }
    stats = compute_run_stats(result, elapsed_ms=1500)
    assert stats["elapsed_s"] == 1.5
    assert stats["pipeline_steps"] == 2
    assert stats["compliance_retries"] == 1
    assert stats["handoffs"] == 1
    assert stats["documents_generated"] == 1
