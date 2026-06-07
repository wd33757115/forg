"""Tests for CLI demo scenarios."""

from langchain_core.messages import HumanMessage

from forge.cli.scenarios import DEMO_SCENARIOS, get_scenario
from forge.core.state import create_initial_state
from forge.core.supervisor import AgentName, Supervisor


def test_get_security_scenario():
    s = get_scenario("security")
    assert s is not None
    assert s.problem_type_hint == "security"


def test_get_itil_alias():
    s = get_scenario("operations")
    assert s is not None
    assert s.id == "itil"


def test_get_mixed_scenario():
    s = get_scenario("mixed")
    assert s is not None
    assert "401" in s.question or "故障" in s.question


def test_demo_scenarios_route_to_problem_solver_not_document():
    """处置方案/应急方案等措辞不应误判为 Document 独立入口。"""
    sup = Supervisor()
    for scenario_id in ("security", "itil", "mixed"):
        scenario = DEMO_SCENARIOS[scenario_id]
        state = create_initial_state(f"route-{scenario_id}")
        state["messages"] = [HumanMessage(content=scenario.question)]
        state["problem_type_hint"] = scenario.problem_type_hint
        decision = sup.decide_initial(state)
        assert decision.next_agent == AgentName.PROBLEM_SOLVER, scenario_id
