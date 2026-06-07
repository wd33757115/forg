"""CLI Demo thinking-chain visualization (C专项) tests."""

from __future__ import annotations

import json

from forge.cli.demo_display import ForgeDemoDisplay
from forge.core.state import create_initial_state
from forge.utils.decision_summary import (
    build_decision_summary_bullets,
    format_decision_summary_markdown,
)
from forge.utils.report import generate_run_report
from forge.utils.trace_export import build_trace_export_payload, write_trace_export


def _sample_result() -> dict:
    state = create_initial_state("demo-c")
    state["run_id"] = "run-c01"
    state["problem_type"] = "security"
    state["last_solution"] = {
        "problem_type": "security",
        "recommended_solution_id": "sol-auth-fix",
        "problem_analysis": "登录 401 与身份鉴别配置相关",
        "confidence": 0.82,
        "rule_pack_references": [{"rule_id": "db-acs-001", "title": "身份鉴别"}],
    }
    state["last_compliance_result"] = {
        "compliance_status": "partial",
        "check_mode": "advisory",
        "risk_level": "medium",
        "failed_items": [
            {
                "rule_id": "db-acs-001",
                "status": "fail",
                "severity": "high",
                "title": "MFA",
            }
        ],
    }
    state["confidence_score"] = 0.75
    state["confidence_recommendation"] = "建议人工复核后执行"
    state["approval_status"] = "auto_approved"
    state["compliance_retry_count"] = 1
    state["pipeline_trace"] = [
        {
            "agent": "problem_solver",
            "status": "success",
            "duration_ms": 90,
            "input_summary": "401",
            "output_summary": "sol-auth-fix",
        }
    ]
    state["conversation_history"] = [
        {
            "event": "handoff",
            "agent": "problem_solver",
            "summary": "交给 compliance",
            "detail": {
                "from_agent": "problem_solver",
                "to_agent": "compliance",
                "payload_keys": ["solution"],
                "handoff_summary": {"rule_ids": ["db-acs-001"], "decision_rationale": "等保身份鉴别"},
            },
        },
        {
            "event": "compliance_check",
            "agent": "compliance",
            "summary": "检查完成",
            "detail": {"compliance_status": "partial", "failed_items_count": 1},
        },
        {
            "event": "thinking",
            "agent": "supervisor",
            "summary": "路由到 problem_solver",
            "detail": {"decision": "security", "evidence": ["401"]},
        },
    ]
    state["_elapsed_ms"] = 1500
    state["final_output"] = {}
    return state


def test_decision_summary_five_bullets():
    result = _sample_result()
    bullets = build_decision_summary_bullets(result)
    assert len(bullets) == 5
    assert "security" in bullets[0]
    assert "sol-auth-fix" in bullets[1]
    assert "partial" in bullets[2]
    assert "75%" in bullets[3] or "0.75" in bullets[3]
    assert "资料" in bullets[4]


def test_decision_summary_markdown_section():
    md = format_decision_summary_markdown(_sample_result())
    assert "## 决策摘要" in md
    assert "**合规闭环**" in md


def test_report_has_decision_summary_and_appendix():
    md = generate_run_report(_sample_result(), question="登录401", elapsed_ms=1500)
    assert "## 决策摘要" in md
    assert "## 附录：完整追踪" in md
    assert "pipeline_trace" in md
    assert "problem_solver" in md
    assert "## 决策链路" not in md


def test_trace_export_payload_and_write(tmp_path):
    result = _sample_result()
    payload = build_trace_export_payload(result, question="登录401")
    assert payload["run_id"] == "run-c01"
    assert len(payload["pipeline_trace"]) == 1
    assert len(payload["conversation_history"]) == 3

    out = write_trace_export(result, tmp_path / "trace.json", question="登录401")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["question"] == "登录401"
    assert data["conversation_history"][0]["event"] == "handoff"


def test_demo_display_plain_includes_summary(capsys):
    display = ForgeDemoDisplay(use_color=False)
    display.print_demo_result(_sample_result(), question="登录401", elapsed_ms=1500, verbose=True)
    out = capsys.readouterr().out
    assert "决策摘要" in out
    assert "sol-auth-fix" in out


def test_demo_display_plain_verbose_shows_thinking(capsys):
    display = ForgeDemoDisplay(use_color=False)
    display.print_demo_result(_sample_result(), verbose=True)
    out = capsys.readouterr().out
    assert "思考链路" in out or "supervisor" in out
