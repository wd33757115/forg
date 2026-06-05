"""LLM integration tests for v1.0 reference-rate acceptance (≥70%).

Run manually when an API key is configured:

    pytest tests/test_llm_reference_coverage.py -m llm -v

Default CI excludes ``-m llm`` tests.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from forge.agents.problem_solver import ProblemSolverAgent
from forge.cli.scenarios import DEMO_SCENARIOS
from forge.core.state import create_initial_state
from forge.utils.metrics import solution_has_rule_references, solution_reference_coverage

_LLM_SCENARIOS = ("security", "itil", "mixed")


@pytest.mark.llm
@pytest.mark.parametrize("scenario_id", _LLM_SCENARIOS)
def test_llm_scenario_has_rule_references(scenario_id: str, require_llm_api_key) -> None:
    """Each standard scenario must produce ≥1 Rule Pack reference with a real LLM."""
    scenario = DEMO_SCENARIOS[scenario_id]
    state = create_initial_state(f"llm-ref-{scenario_id}")
    state["messages"] = [HumanMessage(content=scenario.question)]
    state["problem_type_hint"] = scenario.problem_type_hint
    state["rule_pack"] = {"pack_id": "system_integration_v1", "protection_level": "3"}

    result = ProblemSolverAgent().run(state)
    solution = result.get("last_solution")
    assert solution, f"{scenario_id}: ProblemSolver produced no solution"
    assert solution_has_rule_references(solution), (
        f"{scenario_id}: missing rule_pack_references — "
        f"type={solution.get('problem_type')}"
    )


@pytest.mark.llm
def test_llm_reference_coverage_across_scenarios(require_llm_api_key) -> None:
    """Aggregate reference coverage across security / ITIL / mixed (target ≥70%)."""
    agent = ProblemSolverAgent()
    solutions: list[dict] = []

    for scenario_id in _LLM_SCENARIOS:
        scenario = DEMO_SCENARIOS[scenario_id]
        state = create_initial_state(f"llm-cov-{scenario_id}")
        state["messages"] = [HumanMessage(content=scenario.question)]
        state["problem_type_hint"] = scenario.problem_type_hint
        state["rule_pack"] = {"pack_id": "system_integration_v1", "protection_level": "3"}
        result = agent.run(state)
        solutions.append(result.get("last_solution"))

    coverage = solution_reference_coverage(solutions)
    assert coverage >= 0.7, (
        f"LLM reference coverage {coverage:.0%} below 70% "
        f"({sum(1 for s in solutions if solution_has_rule_references(s))}/{len(solutions)} scenarios)"
    )
