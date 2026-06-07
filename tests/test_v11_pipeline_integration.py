"""Integration test: full v1.1 pipeline including execution and approval."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from forge.core import compile_workflow, create_initial_state


def test_v11_pipeline_execution_approval_trace():
    app = compile_workflow()
    state = create_initial_state("v11-int", current_phase="implementation")
    state["run_id"] = "int01"
    state["messages"] = [HumanMessage(content="等保三级登录401故障，请诊断并整改")]
    state["rule_pack"] = {"pack_id": "system_integration_v1", "protection_level": "3"}
    state["auto_approve"] = True
    state["documents"] = [{"title": "技术方案", "doc_type": "方案"}]
    state["wbs"] = {"req": {"name": "需求"}, "design": {"name": "设计"}}

    result = app.invoke(state)

    assert result.get("last_solution")
    assert result.get("last_compliance_result")
    assert result.get("confidence_score") is not None
    assert result.get("execution_tasks") is not None
    assert result.get("approval_status") in ("auto_approved", "approved", "pending", "blocked")
    if result.get("approval_status") in ("auto_approved", "approved"):
        assert result.get("execution_results") is not None
    trace = result.get("pipeline_trace") or []
    agents = {t.get("agent") for t in trace}
    assert "problem_solver" in agents or "supervisor" in agents
    # At least one trace entry has I/O summary when agents ran
    summarized = [t for t in trace if t.get("input_summary") or t.get("output_summary")]
    assert len(summarized) >= 1
