"""Tests for SecurityAgent and security tools."""

from langchain_core.messages import HumanMessage

from forge.agents.security import SecurityAgent
from forge.agents.security_output import SecurityOutput
from forge.core import create_initial_state
from forge.core.supervisor import Supervisor
from forge.tools.security_tools import build_security_tools, run_security_research


def test_security_intent_detection():
    sup = Supervisor()
    assert sup._is_security_intent("等保三级差距分析")
    assert sup._is_security_intent("防火墙策略审计")
    assert not sup._is_security_intent("数据库连接超时")


def test_security_tools_count():
    state = create_initial_state("sec-test")
    tools = build_security_tools(state)
    assert len(tools) == 6
    assert any(t.name == "query_dengbao_rules" for t in tools)


def test_security_offline_research():
    state = create_initial_state("sec-test")
    state["rule_pack"] = {"protection_level": "3"}
    text = run_security_research(state, "等保三级登录401")
    assert "dengbao_2.0" in text


def test_security_agent_heuristic():
    state = create_initial_state("sec-test", current_phase="implementation")
    state["messages"] = [HumanMessage(content="等保三级登录401故障")]
    state["rule_pack"] = {"protection_level": "3"}
    state["last_solution"] = {
        "problem_analysis": "认证失败",
        "root_causes": ["Token过期"],
        "recommended_solution_id": "sol-a",
        "solutions": [{"id": "sol-a", "title": "修复认证"}],
    }

    result = SecurityAgent().run(state)
    assert result["last_security_result"]
    sec = result["last_security_result"]
    assert sec["protection_level"] == "3"
    assert sec["diagnosis"]
    assert len(sec["configuration_advice"]) >= 1
    assert "security" in result["specialists_completed"]


def test_security_output_json():
    out = SecurityOutput(diagnosis="测试", protection_level="3", risk_assessment="中", risk_level="medium")
    assert "测试" in out.to_display_json()
