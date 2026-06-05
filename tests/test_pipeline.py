"""Tests for pipeline planning and agent runner."""

from forge.core.pipeline import PipelinePlanner, STAGE_COMPLIANCE, STAGE_PROBLEM_SOLVER
from forge.core import create_initial_state
from forge.utils.agent_runner import wrap_agent_node


def test_pipeline_plan_problem_with_security():
    planner = PipelinePlanner()
    plan = planner.build_for_problem_loop(
        "等保三级登录401故障",
        is_security=True,
        is_operations=False,
    )
    assert plan.stages[0] == STAGE_PROBLEM_SOLVER
    assert "security" in plan.stages
    assert STAGE_COMPLIANCE in plan.stages
    assert plan.scenario == "security"


def test_pipeline_plan_operations():
    planner = PipelinePlanner()
    plan = planner.build_for_problem_loop(
        "ITIL事件：核心交换机故障",
        is_security=False,
        is_operations=True,
    )
    assert "operations" in plan.stages
    assert plan.scenario == "operations"


def test_wrap_agent_node_success():
    def ok_agent(state):
        return {"last_solution": {"recommended_solution_id": "sol-a"}}

    node = wrap_agent_node(ok_agent, "test_agent")
    state = create_initial_state("wrap-test")
    state["run_id"] = "test-run"
    result = node(state)
    assert result["last_solution"]
    assert result["pipeline_trace"][-1]["status"] == "success"


def test_wrap_agent_node_failure_optional():
    def fail_agent(state):
        raise RuntimeError("boom")

    node = wrap_agent_node(fail_agent, "security", optional=True)
    state = create_initial_state("wrap-test")
    state["run_id"] = "test-run"
    result = node(state)
    assert result["agent_errors"]
    assert result["pipeline_trace"][-1]["status"] == "failed"
    assert "security" in result["specialists_completed"]
