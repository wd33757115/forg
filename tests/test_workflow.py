"""Tests for LangGraph workflow and closed-loop orchestration."""

from langchain_core.messages import HumanMessage

from forge.core import compile_workflow, create_initial_state
from forge.core.supervisor import is_compliant, is_non_compliant


def test_supervisor_routes_to_compliance_standalone():
    """Standalone 等保 audit: security → compliance → pm_advisor → finalize."""
    app = compile_workflow()
    state = create_initial_state("test-001")
    state["messages"] = [HumanMessage(content="进行等保合规审计")]
    result = app.invoke(state)
    cr = result["compliance_results"][-1]
    assert cr["overall_status"]
    assert cr["risk_level"]
    assert len(cr["results"]) == 3
    assert result["last_compliance_result"] is not None
    assert result["last_security_result"] is not None
    assert result["last_pm_advice"] is not None
    assert result["final_output"]["pm_advice"]
    assert result["final_output"]["security"]
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
    comp_status = result["last_compliance_result"].get("compliance_status")
    assert comp_status in ("compliant", "partial", "non_compliant")
    assert result.get("compliance_retry_count", 0) <= 2

    finalize_msgs = [m for m in result["messages"] if getattr(m, "name", None) == "forge_finalize"]
    assert len(finalize_msgs) == 1
    assert result.get("final_output") is not None
    assert result.get("last_pm_advice") is not None
    assert result["final_output"].get("pm_advice")
    assert result.get("workflow_plan")
    assert len(result.get("pipeline_trace", [])) >= 1

    # DocumentAgent only runs when compliant or partial
    assert len(result.get("conversation_history", [])) >= 4
    if comp_status in ("compliant", "partial"):
        assert len(result.get("generated_documents", [])) == 5
        assert result["final_output"]["document_generation"] == "completed"
    else:
        assert result["final_output"]["document_generation"] == "skipped"


def test_compliance_helpers():
    from forge.core.supervisor import is_partial_compliant, should_generate_documents

    assert is_compliant({"compliance_status": "compliant"})
    assert is_compliant({"overall_status": "pass"})
    assert is_partial_compliant({"compliance_status": "partial"})
    assert should_generate_documents({"compliance_status": "partial"})
    assert is_non_compliant({"compliance_status": "non_compliant"})
    assert is_non_compliant({"overall_status": "critical", "compliance_status": "non_compliant"})


def test_closed_loop_with_security_specialist():
    """等保+故障问题应触发 ProblemSolver → Security → Compliance。"""
    app = compile_workflow()
    state = create_initial_state("test-sec-loop")
    state["messages"] = [HumanMessage(content="等保三级登录401故障，请诊断")]
    state["rule_pack"] = {"pack_id": "system_integration_v1", "protection_level": "3"}
    result = app.invoke(state)

    assert result["last_solution"] is not None
    assert result["last_security_result"] is not None
    assert "security" in result.get("specialists_completed", [])
    assert result["last_compliance_result"] is not None


def test_closed_loop_with_operations_specialist():
    """ITIL 事件问题应触发 ProblemSolver → Operations → Compliance。"""
    app = compile_workflow()
    state = create_initial_state("test-ops-loop")
    state["messages"] = [HumanMessage(content="ITIL事件：核心交换机故障导致业务中断")]
    result = app.invoke(state)

    assert result["last_solution"] is not None
    assert result["last_operations_result"] is not None
    assert "operations" in result.get("specialists_completed", [])
    assert result["last_compliance_result"] is not None


def test_state_has_loop_fields():
    state = create_initial_state("test-003")
    assert state["compliance_retry_count"] == 0
    assert state["last_solution"] is None
    assert state["last_compliance_result"] is None
    assert state["generated_documents"] == []
    assert state["last_pm_advice"] is None
    assert state["last_security_result"] is None
    assert state["last_operations_result"] is None
    assert state["specialist_queue"] == []
    assert state["specialists_completed"] == []
    assert state["workflow_plan"] is None
    assert state["pipeline_trace"] == []
    assert state["agent_errors"] == []
    assert state["final_output"] is None
    assert state["conversation_history"] == []


def test_run_forge_cli_helper():
    from forge.main import run_forge

    result = run_forge("接口超时故障诊断", project_id="test-cli")
    assert result["last_solution"]
    assert result["last_compliance_result"]
