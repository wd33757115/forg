"""Tests for run report Markdown export."""

from __future__ import annotations

from forge.utils.run_report import build_run_report_markdown


def test_build_run_report_contains_key_sections():
    result = {
        "run_id": "abc123",
        "project_id": "demo",
        "problem_type": "security",
        "last_solution": {
            "recommended_solution_id": "sol-1",
            "problem_analysis": "登录故障",
            "problem_type": "security",
        },
        "last_compliance_result": {
            "compliance_status": "partial",
            "check_mode": "advisory",
            "risk_level": "medium",
            "missing_items": ["审计"],
        },
        "generated_documents": [{"doc_type": "solution_summary"}],
        "pipeline_trace": [{"agent": "problem_solver", "status": "success", "detail": "ok"}],
    }
    md = build_run_report_markdown(result, question="测试", scenario="security", elapsed_ms=1200)
    assert "Forge 运行报告" in md
    assert "problem_solver" in md
    assert "partial" in md
    assert "登录故障" in md
