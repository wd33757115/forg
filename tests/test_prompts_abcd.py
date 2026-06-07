"""Tests for prompts A–D quality polish (ProblemSolver + Compliance + loader)."""

from __future__ import annotations

from forge.agents.compliance import ComplianceAgent
from forge.agents.compliance_output import ComplianceOutput
from forge.agents.problem_solver import ProblemSolverAgent
from forge.agents.solution_output import SolutionOption, SolutionOutput
from forge.core.state import WORKFLOW_PROBLEM_COMPLIANCE_LOOP, create_initial_state
from forge.prompts.loader import get_prompt, load_prompts
from forge.utils.compliance_explain import enrich_compliance_output
from forge.utils.metrics import solution_has_rule_references
from langchain_core.messages import HumanMessage


def test_solution_output_reasoning_and_confidence():
    sol = SolutionOutput(
        problem_type="security",
        problem_analysis="401",
        root_causes=["证书过期"],
        rule_pack_references=[],
        solutions=[
            SolutionOption(
                id="sol-a",
                title="A",
                description="d",
                approach="a",
                compliance_impact="db-acs-001",
                itil_guidance="itil-inc-001",
            ),
            SolutionOption(
                id="sol-b",
                title="B",
                description="d2",
                approach="a2",
                compliance_impact="db-aud-001",
                itil_guidance="itil-chg-001",
            ),
        ],
        recommended_solution_id="sol-a",
        next_actions=["step"],
    )
    ProblemSolverAgent._ensure_reasoning_confidence(sol)
    ProblemSolverAgent._ensure_decision_rationale(sol)
    assert sol.reasoning
    assert 0.0 < sol.confidence <= 1.0


def test_problem_solver_rule_refs_offline():
    state = create_initial_state("abcd-ps")
    state["active_workflow"] = WORKFLOW_PROBLEM_COMPLIANCE_LOOP
    state["messages"] = [HumanMessage(content="等保三级登录401认证失败")]
    result = ProblemSolverAgent().run(state)
    sol = result["last_solution"]
    assert solution_has_rule_references(sol)
    assert len(sol.get("rule_pack_references") or []) >= 3
    assert sol.get("reasoning")
    assert sol.get("confidence") is not None


def test_compliance_explainability_fields_strict_vs_lenient():
    from forge.agents.compliance_output import CheckItem, ModuleComplianceResult

    output = ComplianceOutput(
        overall_status="gaps_found",
        risk_level="medium",
        results=[
            ModuleComplianceResult(
                module="dengbao_2.0",
                module_name="等保",
                status="gaps_found",
                score=60.0,
                items=[
                    CheckItem(
                        check_id="c1",
                        title="身份鉴别",
                        category="dengbao_2.0",
                        status="fail",
                        detail="MFA 缺失",
                        rule_id="db-acs-001",
                    ),
                    CheckItem(
                        check_id="c2",
                        title="审计",
                        category="dengbao_2.0",
                        status="warning",
                        detail="日志保留",
                        rule_id="db-aud-001",
                    ),
                ],
                summary="缺口",
            )
        ],
        missing_items=["MFA"],
        recommendations=[],
        next_action="整改",
    )
    strict = enrich_compliance_output(output, check_mode="strict")
    lenient = enrich_compliance_output(output, check_mode="lenient")
    assert "db-acs-001" in strict.matched_rules
    assert len(strict.failed_items) >= 2
    assert len(lenient.failed_items) == 1
    assert strict.suggestions


def test_compliance_agent_persists_matched_rules():
    state = create_initial_state("abcd-cmp")
    state["messages"] = [HumanMessage(content="合规检查")]
    state["rule_pack"] = {"protection_level": "3"}
    state["wbs"] = {"design": {"name": "设计", "status": "done"}}
    agent = ComplianceAgent()
    updates = agent.run(state)
    structured = updates["last_compliance_result"]
    assert structured.get("matched_rules") is not None
    assert "check_explanations" in structured


def test_get_prompt_loader():
    text = get_prompt("problem_solver", "PROBLEM_SOLVER_SYSTEM")
    assert "ProblemSolverAgent" in text
    mod = load_prompts("compliance")
    assert hasattr(mod, "COMPLIANCE_SYSTEM")
