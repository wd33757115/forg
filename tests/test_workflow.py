"""Tests for LangGraph workflow."""

from langchain_core.messages import HumanMessage

from forge.core import compile_workflow, create_initial_state


def test_supervisor_routes_to_compliance():
    app = compile_workflow()
    state = create_initial_state("test-001")
    state["messages"] = [HumanMessage(content="进行等保合规审计")]
    result = app.invoke(state)
    assert result["next_agent"] == "compliance"
    assert len(result["compliance_history"]) == 1
    assert len(result["compliance_results"]) == 1
    assert result["rule_pack"] is not None
    assert result["rule_pack"]["pack_id"] == "system_integration_v1"


def test_supervisor_routes_to_problem_solver():
    app = compile_workflow()
    state = create_initial_state("test-002")
    state["messages"] = [HumanMessage(content="系统出现故障，需要根因分析")]
    result = app.invoke(state)
    assert result["next_agent"] == "problem_solver"
    assert len(result["knowledge_base"]) == 1
