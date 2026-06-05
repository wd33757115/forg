"""Tests for ComplianceAgent, tools, and ComplianceOutput."""

import json

import pytest
from langchain_core.messages import HumanMessage

from forge.agents.compliance import ComplianceAgent
from forge.agents.compliance_output import ComplianceOutput
from forge.agents.solution_output import SolutionOption, SolutionOutput
from forge.core import compile_workflow, create_initial_state
from forge.tools.compliance_tools import (
    build_compliance_tools,
    check_base_compliance,
    check_dengbao_compliance,
    check_itil_compliance,
    run_all_compliance_checks,
)


@pytest.fixture
def base_state():
    state = create_initial_state("cmp-test-001", current_phase="implementation")
    state["wbs"] = {"design": {"name": "设计", "status": "done"}}
    state["messages"] = [HumanMessage(content="进行等保三级合规检查")]
    state["rule_pack"] = {"pack_id": "system_integration_v1", "protection_level": "3"}
    return state


def test_compliance_tools_count(base_state):
    tools = build_compliance_tools(base_state)
    assert {t.name for t in tools} == {
        "check_base_compliance",
        "check_dengbao_compliance",
        "check_itil_compliance",
    }


def test_check_base_compliance(base_state):
    result = check_base_compliance(base_state)
    assert result["module"] == "base_si"
    assert result["status"] in ("pass", "gaps_found")
    assert len(result["items"]) >= 1


def test_check_dengbao_host_network_audit(base_state):
    result = check_dengbao_compliance(base_state, "3")
    titles = {item["title"] for item in result["items"]}
    assert "安全计算环境（主机安全）" in titles
    assert "安全通信网络 / 区域边界（网络安全）" in titles
    assert "安全审计" in titles


def test_check_itil_processes(base_state):
    result = check_itil_compliance(base_state)
    titles = {item["title"] for item in result["items"]}
    assert "事件管理" in titles
    assert "变更管理" in titles
    assert "配置管理" in titles
    assert "问题管理" in titles


def test_run_all_modules(base_state):
    raw = run_all_compliance_checks(base_state)
    assert set(raw["modules"].keys()) == {"base_si", "dengbao_2.0", "itil_iso20000"}


def test_compliance_agent_heuristic_output(base_state):
    agent = ComplianceAgent()
    output = agent.run_compliance(base_state, skip_react=True)
    assert isinstance(output, ComplianceOutput)
    assert output.overall_status in ("pass", "gaps_found", "critical")
    assert output.risk_level in ("low", "medium", "high", "critical")
    assert len(output.results) == 3
    assert output.next_action


def test_validate_solution_integration(base_state):
    solution = SolutionOutput(
        problem_analysis="登录认证故障",
        root_causes=["证书过期"],
        solutions=[
            SolutionOption(
                id="sol-a",
                title="更新证书",
                description="更新 SSO 证书",
                approach="轮换证书",
                compliance_impact="满足身份鉴别要求",
                itil_guidance="变更管理",
            )
        ],
        recommended_solution_id="sol-a",
        next_actions=["更新证书"],
    )
    agent = ComplianceAgent()
    validation = agent.validate_solution(base_state, solution)
    assert isinstance(validation, ComplianceOutput)
    assert validation.protection_level == "3"


def test_agent_run_persists_structured_results(base_state):
    agent = ComplianceAgent()
    result = agent.run(base_state)
    assert result["compliance_results"]
    structured = result["compliance_results"][-1]
    assert "overall_status" in structured
    assert "results" in structured
    assert "risk_level" in structured


def test_problem_solver_sets_last_solution_in_loop():
    from forge.agents.problem_solver import ProblemSolverAgent
    from forge.core.state import WORKFLOW_PROBLEM_COMPLIANCE_LOOP

    state = create_initial_state("cmp-ps-001")
    state["active_workflow"] = WORKFLOW_PROBLEM_COMPLIANCE_LOOP
    state["messages"] = [HumanMessage(content="登录401故障")]
    result = ProblemSolverAgent().run(state)
    assert result["last_solution"] is not None
    assert result["last_solution"]["recommended_solution_id"]


def test_workflow_compliance_route():
    app = compile_workflow()
    state = create_initial_state("cmp-wf-001")
    state["messages"] = [HumanMessage(content="等保测评缺口整改")]
    result = app.invoke(state)
    assert result["next_agent"] == "__end__"
    assert result["last_compliance_result"] is not None
    cr = result["last_compliance_result"]
    assert cr["overall_status"]
    assert len(cr["results"]) == 3
