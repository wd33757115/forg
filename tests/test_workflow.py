"""Tests for LangGraph workflow and closed-loop orchestration."""

from langchain_core.messages import HumanMessage

from forge.core import compile_workflow, create_initial_state
from forge.core.supervisor import is_compliant, is_non_compliant


def test_supervisor_routes_to_compliance_standalone():
    """Standalone compliance audit: compliance → finalize."""
    app = compile_workflow()
    state = create_initial_state("test-001")
    state["messages"] = [HumanMessage(content="进行等保合规审计")]
    result = app.invoke(state)
    cr = result["compliance_results"][-1]
    assert cr["overall_status"]
    assert cr["risk_level"]
    assert len(cr["results"]) == 3
    assert result["last_compliance_result"] is not None
    assert result["rule_pack"]["pack_id"] == "system_integration_v1"


def test_closed_loop_problem_solver_compliance():
    """Problem query triggers ProblemSolver → Compliance → Finalize loop."""
    app = compile_workflow()
    state = create_initial_state("test-002")
    state["messages"] = [HumanMessage(content="系统出现故障，需要根因分析")]
    result = app.invoke(state)

    assert result["last_solution"] is not None
    assert result["last_compliance_result"] is not None
    assert "recommended_solution_id" in result["last_solution"]
    assert result["last_compliance_result"].get("compliance_status") in (
        "compliant",
        "non_compliant",
    )
    assert result.get("compliance_retry_count", 0) <= 2

    finalize_msgs = [m for m in result["messages"] if getattr(m, "name", None) == "forge_finalize"]
    assert len(finalize_msgs) == 1


def test_compliance_helpers():
    assert is_compliant({"compliance_status": "compliant"})
    assert is_compliant({"overall_status": "pass"})
    assert is_non_compliant({"compliance_status": "non_compliant"})
    assert is_non_compliant({"overall_status": "gaps_found"})


def test_state_has_loop_fields():
    state = create_initial_state("test-003")
    assert state["compliance_retry_count"] == 0
    assert state["last_solution"] is None
    assert state["last_compliance_result"] is None


def test_run_forge_cli_helper():
    from forge.main import run_forge

    result = run_forge("接口超时故障诊断", project_id="test-cli")
    assert result["last_solution"]
    assert result["last_compliance_result"]
