"""Tests for PMAdvisorAgent, tools, and output models."""

from langchain_core.messages import HumanMessage

from forge.agents.pm_advisor import PMAdvisorAgent
from forge.agents.pm_advisor_output import PMAdvisorOutput
from forge.core import create_initial_state
from forge.tools.pm_advisor_tools import build_pm_advisor_tools, run_pm_advisor_research


def test_pm_advisor_tools_count():
    state = create_initial_state("pm-test")
    tools = build_pm_advisor_tools(state)
    names = {t.name for t in tools}
    assert len(tools) == 5
    assert "get_solution_summary" in names
    assert "get_compliance_summary" in names
    assert "get_project_memory" in names


def test_pm_advisor_offline_research():
    state = create_initial_state("pm-test")
    state["last_solution"] = {
        "recommended_solution_id": "sol-a",
        "problem_analysis": "登录认证失败",
        "root_causes": ["会话过期"],
        "solutions": [{"id": "sol-a", "title": "修复认证"}],
        "next_actions": ["检查 IdP 配置"],
    }
    state["last_compliance_result"] = {
        "compliance_status": "partial",
        "risk_level": "medium",
        "missing_items": ["审计日志"],
        "recommendations": ["补齐审计"],
    }
    text = run_pm_advisor_research(state, "登录401故障")
    assert "方案摘要" in text
    assert "合规摘要" in text


def test_pm_advisor_agent_run_heuristic():
    state = create_initial_state("pm-test", current_phase="implementation")
    state["messages"] = [HumanMessage(content="等保三级登录401故障")]
    state["last_solution"] = {
        "recommended_solution_id": "sol-a",
        "problem_analysis": "认证链路异常导致401",
        "root_causes": ["Token 校验失败"],
        "solutions": [
            {
                "id": "sol-a",
                "title": "统一认证修复",
                "description": "修复 SSO 与会话管理",
            }
        ],
        "next_actions": ["验证登录流程", "更新审计策略"],
    }
    state["last_compliance_result"] = {
        "compliance_status": "non_compliant",
        "risk_level": "high",
        "missing_items": ["双因素认证证据", "审计留存"],
        "recommendations": ["部署 MFA", "集中审计"],
    }
    state["compliance_retry_count"] = 2

    agent = PMAdvisorAgent()
    result = agent.run(state)

    assert result["last_pm_advice"] is not None
    advice = result["last_pm_advice"]
    assert advice["summary"]
    assert len(advice["action_items"]) >= 1
    assert len(advice["risks"]) >= 1
    assert advice["report_outline"]
    assert any(e.get("event") == "pm_advice_generated" for e in result["conversation_history"])


def test_pm_advisor_output_json():
    output = PMAdvisorOutput(
        summary="测试摘要",
        situation_overview="现状",
        key_findings=["发现1"],
        recommendations=["建议1"],
    )
    assert "测试摘要" in output.to_display_json()
