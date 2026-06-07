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
    assert result.get("memory_graph") is not None or result.get("knowledge_base")


def test_v11_local_manifest_via_approval_gate(tmp_path, monkeypatch):
    """Approval gate with local_manifest writes manifest and execution_results."""
    from forge.config import ForgeSettings, reset_settings_cache
    from forge.core.approval.node import approval_gate_node
    from forge.core.execution.node import execution_node
    import forge.core.execution.backend as backend_mod

    settings = ForgeSettings.model_construct(
        llm_provider="deepseek",
        deepseek_api_key=None,
        openai_api_key=None,
        dashscope_api_key=None,
        aliyun_api_key=None,
        volc_api_key=None,
        ark_api_key=None,
        openai_base_url=None,
        llm_model=None,
        llm_temperature=0.3,
        llm_max_retries=0,
        llm_retry_delay=0.0,
        llm_timeout=5.0,
        llm_structured_mode="auto",
        compliance_check_mode="advisory",
        execution_mode="local_manifest",
        execution_manifest_dir=str(tmp_path),
        execution_webhook_url=None,
        execution_webhook_timeout=30.0,
        log_level="WARNING",
        web_host="127.0.0.1",
        web_port=8000,
    )
    monkeypatch.setattr(backend_mod, "get_settings", lambda: settings)

    state = create_initial_state("v11-manifest")
    state["run_id"] = "m01"
    state["auto_approve"] = True
    state["execution_mode"] = "local_manifest"
    state["last_solution"] = {
        "problem_type": "security",
        "recommended_solution_id": "sol-a",
        "problem_analysis": "401",
        "rule_pack_references": [{"rule_id": "db-acs-001"}],
    }
    state["last_compliance_result"] = {
        "compliance_status": "compliant",
        "evidence_coverage": 0.9,
        "results": [{"items": [{"rule_id": "db-acs-001"}]}],
        "missing_items": [],
    }
    state.update(execution_node(state))
    result = approval_gate_node(state)
    reset_settings_cache()

    assert result.get("execution_results")
    meta = result["execution_results"][0].get("metadata") or {}
    assert meta.get("backend") == "local_manifest"
    assert list(tmp_path.glob("exec_m01_*.json"))
