"""Tests for ProblemSolverAgent, tools, and SolutionOutput."""

import json

import pytest
from langchain_core.messages import HumanMessage

from forge.agents.problem_solver import ProblemSolverAgent
from forge.agents.solution_output import SolutionOutput
from forge.core import create_initial_state
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


def test_heuristic_solution_output_auth(base_state):
    agent = ProblemSolverAgent()
    research = run_tool_research(base_state, "用户登录接口返回401")
    solution = agent._build_heuristic_solution(base_state, "用户登录接口返回401", research)

    assert isinstance(solution, SolutionOutput)
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
