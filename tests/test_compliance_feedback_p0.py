"""P0: structured compliance retry feedback + PS confidence caps."""

from __future__ import annotations

from forge.agents.problem_solver import ProblemSolverAgent
from forge.agents.solution_output import SolutionOutput, SolutionOption
from forge.core.confidence.config import PS_HEURISTIC_CONFIDENCE_CAP
from forge.core.state import create_initial_state
from forge.core.supervisor import Supervisor, WorkflowStep
from forge.utils.compliance_feedback import (
    build_compliance_feedback,
    format_compliance_feedback_for_prompt,
)


def test_build_compliance_feedback_includes_failed_items():
    compliance = {
        "compliance_status": "non_compliant",
        "check_mode": "strict",
        "risk_level": "high",
        "failed_items": [
            {
                "rule_id": "db-acs-001",
                "severity": "high",
                "status": "fail",
                "title": "身份鉴别",
                "suggestion": "启用 MFA",
            }
        ],
        "missing_items": ["缺审计报告"],
    }
    fb = build_compliance_feedback(compliance, retry_count=1)
    assert fb["retry_count"] == 1
    assert fb["failed_rule_ids"] == ["db-acs-001"]
    text = format_compliance_feedback_for_prompt(fb)
    assert "db-acs-001" in text
    assert "MFA" in text


def test_supervisor_retry_sets_compliance_feedback():
    state = create_initial_state("retry-fb")
    state["workflow_step"] = WorkflowStep.RETRY
    state["last_compliance_result"] = {
        "compliance_status": "non_compliant",
        "check_mode": "strict",
        "risk_level": "medium",
        "failed_items": [
            {
                "rule_id": "db-acs-001",
                "severity": "high",
                "status": "fail",
                "title": "MFA",
                "suggestion": "配置双因素",
            }
        ],
    }
    result = Supervisor()(state)
    assert result.get("compliance_feedback")
    assert result["compliance_feedback"]["failed_rule_ids"] == ["db-acs-001"]
    assert result["compliance_retry_count"] == 1


def test_confidence_min_llm_and_heuristic_cap():
    output = SolutionOutput(
        problem_analysis="分析",
        root_causes=["a"],
        solutions=[
            SolutionOption(
                id="sol-a",
                title="A",
                description="d",
                approach="ap",
            ),
            SolutionOption(
                id="sol-b",
                title="B",
                description="d",
                approach="ap",
            ),
        ],
        recommended_solution_id="sol-a",
        next_actions=["act"],
        confidence=0.95,
        rule_pack_references=[],
    )
    ProblemSolverAgent._finalize_confidence(
        output, research_context="", solution_source="llm"
    )
    assert output.confidence <= 0.95

    output.confidence = 0.95
    ProblemSolverAgent._finalize_confidence(
        output, research_context="", solution_source="heuristic"
    )
    assert output.confidence <= PS_HEURISTIC_CONFIDENCE_CAP


def test_apply_compliance_feedback_adds_next_actions():
    output = SolutionOutput(
        problem_analysis="分析",
        root_causes=["a"],
        solutions=[
            SolutionOption(id="sol-a", title="A", description="d", approach="ap"),
            SolutionOption(id="sol-b", title="B", description="d", approach="ap"),
        ],
        recommended_solution_id="sol-a",
        next_actions=["原有动作"],
        reasoning="1) 类型=security",
    )
    feedback = build_compliance_feedback(
        {
            "compliance_status": "non_compliant",
            "failed_items": [
                {
                    "rule_id": "db-acs-001",
                    "severity": "high",
                    "status": "fail",
                    "suggestion": "启用 MFA",
                }
            ],
        },
        retry_count=1,
    )
    ProblemSolverAgent._apply_compliance_feedback_to_output(output, feedback)
    assert any("db-acs-001" in a for a in output.next_actions)
    assert "合规重试" in output.reasoning
