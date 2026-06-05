"""Integration tests for standard demo scenarios (offline heuristic path)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from forge.agents.compliance import ComplianceAgent
from forge.agents.compliance_output import ComplianceOutput
from forge.cli.demo_seed import apply_demo_evidence_seed
from forge.cli.scenarios import DEMO_SCENARIOS
from forge.core.workflow import compile_workflow
from forge.core.state import create_initial_state
from forge.utils.metrics import (
    compliance_rule_id_mapping_rate,
    solution_has_rule_references,
)


@pytest.mark.parametrize("scenario_id", ["security", "itil", "mixed"])
def test_standard_scenario_closed_loop_offline(scenario_id: str):
    """Demo scenarios must enter ProblemSolver closed loop and produce core artifacts."""
    scenario = DEMO_SCENARIOS[scenario_id]
    state = create_initial_state(f"integ-{scenario_id}")
    state["run_id"] = f"test-{scenario_id}"
    state["messages"] = [HumanMessage(content=scenario.question)]
    state["problem_type_hint"] = scenario.problem_type_hint
    state["rule_pack"] = {"pack_id": "system_integration_v1", "protection_level": "3"}
    state["check_mode"] = "advisory"
    state = apply_demo_evidence_seed(state)

    result = compile_workflow().invoke(state)

    assert result.get("last_solution"), f"{scenario_id}: missing solution"
    assert result.get("last_compliance_result"), f"{scenario_id}: missing compliance"
    assert solution_has_rule_references(result.get("last_solution"))
    assert result.get("last_pm_advice"), f"{scenario_id}: missing PM advice"
    assert result.get("final_output") is not None

    comp_status = result["last_compliance_result"].get("compliance_status")
    assert comp_status in ("compliant", "partial", "non_compliant")
    if comp_status in ("compliant", "partial"):
        docs = result.get("generated_documents") or []
        assert len(docs) >= 1, f"{scenario_id}: expected documents when {comp_status}"
    else:
        assert result["final_output"].get("document_generation") == "skipped"


@pytest.mark.parametrize("scenario_id", ["security", "itil", "mixed"])
def test_standard_scenario_compliance_rule_ids(scenario_id: str):
    scenario = DEMO_SCENARIOS[scenario_id]
    state = create_initial_state(f"integ-cmp-{scenario_id}")
    state["messages"] = [HumanMessage(content=scenario.question)]
    state["rule_pack"] = {"protection_level": "3"}
    output = ComplianceAgent().run_compliance(state, skip_react=True)
    assert isinstance(output, ComplianceOutput)
    assert compliance_rule_id_mapping_rate(output) >= 0.8
