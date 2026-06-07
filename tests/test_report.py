"""Tests for utils/report.py."""

from __future__ import annotations

from forge.core.state import create_initial_state
from forge.utils.report import default_report_path, generate_run_report, save_run_report


def test_generate_run_report_sections():
    state = create_initial_state("report-test")
    state["run_id"] = "r001"
    state["last_solution"] = {
        "recommended_solution_id": "sol-1",
        "problem_analysis": "分析内容",
        "problem_type": "security",
        "rule_pack_references": [{"rule_id": "db-001", "title": "审计"}],
    }
    state["last_compliance_result"] = {
        "compliance_status": "partial",
        "check_mode": "advisory",
        "risk_level": "medium",
        "missing_items": ["缺口A"],
        "check_explanations": [
            {
                "module": "dengbao_2.0",
                "rule_id": "db-acs-001",
                "status": "fail",
                "explanation": "[FAIL] 身份鉴别 rule_id=db-acs-001: MFA 缺失",
            }
        ],
    }
    state["last_solution"]["decision_rationale"] = "推荐 sol-1 基于 db-001"
    state["pipeline_trace"] = [
        {
            "agent": "problem_solver",
            "status": "success",
            "duration_ms": 120,
            "input_summary": "问题: 401",
            "output_summary": "sol-1",
        }
    ]
    state["conversation_history"] = [
        {"event": "compliance_retry", "agent": "supervisor", "summary": "重试", "detail": {}},
        {
            "event": "thinking",
            "agent": "supervisor",
            "summary": "路由",
            "detail": {"decision": "进入 problem_solver", "evidence": ["security"]},
        },
    ]
    md = generate_run_report(state, question="登录401", elapsed_ms=2000)
    assert "Forge 运行报告" in md
    assert "登录401" in md
    assert "pipeline_trace" in md
    assert "合规重试" in md
    assert "关键决策" in md
    assert "决策依据" in md
    assert "合规检查追溯" in md
    assert "input_summary" not in md  # rendered in table, not raw key
    assert "problem_solver" in md


def test_save_run_report_to_reports_dir(tmp_path, monkeypatch):
    state = create_initial_state("save-rpt")
    state["run_id"] = "abc99"
    monkeypatch.chdir(tmp_path)
    path = save_run_report(state, question="q")
    assert path.resolve() == (tmp_path / "reports" / "run_abc99.md").resolve()
    assert path.exists()
    assert default_report_path(state).name == "run_abc99.md"
