"""Tests for v1.0 quality metrics."""

from __future__ import annotations

from forge.agents.compliance import ComplianceAgent
from forge.agents.compliance_output import CheckItem, ComplianceOutput, ModuleComplianceResult
from forge.agents.problem_solver import ProblemSolverAgent
from forge.core.state import create_initial_state
from forge.utils.metrics import (
    compliance_rule_id_mapping_rate,
    solution_reference_coverage,
)
from langchain_core.messages import HumanMessage


def test_compliance_rule_id_mapping_rate_heuristic():
    state = create_initial_state("metrics-cmp")
    state["messages"] = [HumanMessage(content="等保三级合规检查")]
    state["rule_pack"] = {"protection_level": "3"}
    output = ComplianceAgent().run_compliance(state, skip_react=True)
    rate = compliance_rule_id_mapping_rate(output)
    assert rate >= 0.8, f"rule_id mapping rate {rate:.0%} below 80%"


def test_solution_reference_coverage_standard_scenarios():
    scenarios = [
        ("等保三级登录401认证失败", "security"),
        ("ITIL事件：核心交换机中断导致SLA违约", "service_management"),
        ("等保测评缺口且变更未走CAB", "mixed"),
    ]
    agent = ProblemSolverAgent()
    solutions: list[dict] = []
    for question, ptype in scenarios:
        state = create_initial_state(f"metrics-ps-{ptype}")
        state["messages"] = [HumanMessage(content=question)]
        state["problem_type_hint"] = ptype if ptype != "service_management" else "itil"
        result = agent.run(state)
        solutions.append(result.get("last_solution"))
    coverage = solution_reference_coverage(solutions)
    assert coverage >= 0.7, f"reference coverage {coverage:.0%} below 70%"


def test_compliance_rule_id_mapping_rate_unit():
    output = ComplianceOutput(
        overall_status="gaps_found",
        risk_level="medium",
        results=[
            ModuleComplianceResult(
                module="dengbao_2.0",
                status="gaps_found",
                score=50.0,
                items=[
                    CheckItem(
                        check_id="db-host",
                        title="t",
                        category="dengbao_2.0",
                        status="fail",
                        rule_id="db-acs-001",
                    ),
                    CheckItem(
                        check_id="x",
                        title="y",
                        category="dengbao_2.0",
                        status="fail",
                        rule_id="",
                        rule_reference="",
                    ),
                ],
            )
        ],
    )
    assert compliance_rule_id_mapping_rate(output) == 0.5
