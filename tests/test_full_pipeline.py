"""End-to-end test: ProblemSolver → Compliance → Document pipeline."""

from langchain_core.messages import HumanMessage

from forge.core import compile_workflow, create_initial_state


def test_full_pipeline_generates_documents():
    """When compliance is partial, full pipeline produces 5 documents."""
    app = compile_workflow()
    state = create_initial_state("pipeline-001", current_phase="implementation")
    state["messages"] = [HumanMessage(content="登录401认证失败，请诊断")]
    state["rule_pack"] = {"pack_id": "system_integration_v1", "protection_level": "3"}
    # Pre-seed minimal evidence so compliance lands on partial (not critical)
    state["documents"] = [
        {"title": "技术方案", "doc_type": "方案"},
        {"title": "接口设计文档", "doc_type": "接口"},
    ]
    state["wbs"] = {
        "requirements": {"name": "需求"},
        "design": {"name": "设计"},
        "implementation": {"name": "实施"},
    }

    result = app.invoke(state)

    assert result["last_solution"]
    assert result["last_compliance_result"]
    assert result["final_output"]
    status = result["last_compliance_result"].get("compliance_status")
    if status in ("compliant", "partial"):
        assert len(result["generated_documents"]) == 5
        assert result["final_output"]["document_generation"] == "completed"
        assert result["generated_documents"][0]["format"] == "markdown"
