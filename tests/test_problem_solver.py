"""Tests for ProblemSolverAgent, tools, and SolutionOutput."""

import json

import pytest
from langchain_core.messages import HumanMessage

from forge.agents.problem_classifier import classify_problem
from forge.agents.problem_solver import ProblemSolverAgent
from forge.agents.solution_output import SolutionOutput
from forge.core import create_initial_state
from forge.core.tool_registry import get_tool_registry
from forge.tools.problem_solver_tools import (
    build_problem_solver_tools,
    run_tool_research,
)


@pytest.fixture
def base_state():
    state = create_initial_state("ps-test-001", current_phase="implementation")
    state["wbs"] = {
        "design": {"name": "方案设计", "status": "in_progress"},
        "implementation": {"name": "实施部署", "status": "pending"},
    }
    state["messages"] = [HumanMessage(content="用户登录接口返回401，请帮忙诊断")]
    return state


def test_build_problem_solver_tools_count(base_state):
    tools = build_problem_solver_tools(base_state)
    names = {t.name for t in tools}
    assert names == {
        "get_current_project_state",
        "query_rule_pack",
        "get_dengbao_requirements",
        "get_itil_guidance",
        "analyze_impact",
        "search_historical_cases",
    }


def test_get_current_project_state_tool(base_state):
    tools = build_problem_solver_tools(base_state)
    tool = next(t for t in tools if t.name == "get_current_project_state")
    result = json.loads(tool.invoke({}))
    assert result["project_id"] == "ps-test-001"
    assert "design" in result["wbs_items"]


def test_query_rule_pack_tool(base_state):
    tools = build_problem_solver_tools(base_state)
    tool = next(t for t in tools if t.name == "query_rule_pack")
    result = json.loads(tool.invoke({"module": "dengbao_2.0", "category": "", "keyword": ""}))
    assert len(result) >= 1
    assert result[0]["module"] == "dengbao_2.0"


def test_get_dengbao_requirements_tool(base_state):
    tools = build_problem_solver_tools(base_state)
    tool = next(t for t in tools if t.name == "get_dengbao_requirements")
    result = json.loads(tool.invoke({"level": "3"}))
    assert result["level"] == "3"
    assert len(result["level_requirements"]) >= 1


def test_get_itil_guidance_tool(base_state):
    tools = build_problem_solver_tools(base_state)
    tool = next(t for t in tools if t.name == "get_itil_guidance")
    result = json.loads(tool.invoke({"practice": "incident"}))
    assert result["practice"] == "Incident Management"


def test_run_tool_research(base_state):
    research = run_tool_research(base_state, "登录401认证失败")
    assert "project_state" in research
    assert "dengbao_l3" in research


@pytest.mark.parametrize(
    "question,hint,expected",
    [
        ("等保三级登录401认证失败", "security", "security"),
        ("ITIL事件核心交换机中断SLA违约", "itil", "service_management"),
        ("数据库连接池耗尽导致超时", "general", "technical"),
    ],
)
def test_classify_problem_types(question, hint, expected):
    ptype, _reason = classify_problem(question, hint=hint)
    assert ptype == expected


@pytest.mark.parametrize(
    "question,expected",
    [
        ("用户登录接口返回401请诊断", "security"),
        ("ITIL事件核心交换机中断SLA违约", "service_management"),
        ("数据库连接池耗尽导致接口超时", "technical"),
        ("等保401认证失败同时核心交换机故障中断", "mixed"),
    ],
)
def test_classify_problem_auto_without_hint(question, expected):
    """Auto classification without CLI hint (security / itil / general)."""
    ptype, _reason = classify_problem(question)
    assert ptype == expected


def test_classify_auth_fault_not_mixed_with_generic_fault_keyword():
    """401 + 故障 should stay security, not mixed."""
    ptype, _ = classify_problem("登录401认证故障请诊断")
    assert ptype == "security"


def test_heuristic_solution_has_at_least_three_rule_refs(base_state):
    agent = ProblemSolverAgent()
    research = run_tool_research(base_state, "用户登录接口返回401")
    solution = agent._build_heuristic_solution(
        base_state,
        "用户登录接口返回401",
        research,
        "security",
        "命中等保/安全关键词",
    )
    validated = agent._validate_solution_output(
        solution,
        problem_statement="用户登录接口返回401",
        problem_type="security",
        research_context=research,
    )
    assert len(validated.rule_pack_references) >= 3
    for ref in validated.rule_pack_references:
        assert ref.rule_id.startswith(("db-", "itil-", "si-"))


def test_problem_solver_resolves_tools_via_registry(base_state):
    agent = ProblemSolverAgent()
    registry = get_tool_registry()
    registry_tools = registry.get_tools("problem_solver", base_state)
    agent_tools = agent.get_tools(base_state)
    assert {t.name for t in agent_tools} == {t.name for t in registry_tools}


def test_heuristic_solution_output_auth(base_state):
    agent = ProblemSolverAgent()
    research = run_tool_research(base_state, "用户登录接口返回401")
    solution = agent._build_heuristic_solution(
        base_state,
        "用户登录接口返回401",
        research,
        "security",
        "命中等保/安全关键词",
    )

    assert isinstance(solution, SolutionOutput)
    assert solution.problem_type == "security"
    assert len(solution.rule_pack_references) >= 3
    assert len(solution.solutions) >= 2
    assert solution.recommended_solution_id in {s.id for s in solution.solutions}
    assert len(solution.root_causes) >= 1
    assert len(solution.next_actions) >= 1
    assert len(solution.dengbao_considerations) >= 1
    assert len(solution.itil_considerations) >= 1


def test_agent_run_produces_structured_knowledge(base_state):
    agent = ProblemSolverAgent()
    result = agent.run(base_state)

    assert result.get("messages")
    kb = result["knowledge_base"]
    assert len(kb) == 1
    assert kb[0]["category"] == "problem_solution"
    assert "solution" in kb[0]["metadata"]
    assert kb[0]["metadata"]["recommended_solution_id"]
    assert result.get("problem_type")
    assert result.get("agent_context", {}).get("compliance")
    solution = result.get("last_solution") or {}
    assert len(solution.get("rule_pack_references") or []) >= 3
    assert "现象：" in solution.get("problem_analysis", "")


def test_solution_output_json_schema():
    sol = SolutionOutput(
        problem_analysis="test",
        root_causes=["a"],
        solutions=[],
        recommended_solution_id="sol-a",
        next_actions=["act"],
    )
    # validation pads solutions in agent; raw model allows empty for this test
    data = sol.model_dump()
    assert "problem_analysis" in data
    assert "recommended_solution_id" in data
