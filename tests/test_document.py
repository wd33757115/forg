"""Tests for DocumentAgent and document generation tools."""

from forge.agents.document import DocumentAgent
from forge.core import create_initial_state
from forge.core.supervisor import is_partial_compliant, should_generate_documents
from forge.tools.document_tools import generate_document_bundle


def test_generate_document_bundle():
    solution = {
        "recommended_solution_id": "sol-a",
        "problem_analysis": "登录认证故障",
        "root_causes": ["证书过期"],
        "solutions": [
            {
                "id": "sol-a",
                "title": "更新证书",
                "description": "轮换 SSO 证书",
                "approach": "更新并同步",
                "compliance_impact": "满足身份鉴别",
                "itil_guidance": "变更管理",
                "trade_offs": [],
                "risk_level": "low",
            }
        ],
        "next_actions": ["更新证书"],
        "dengbao_considerations": ["身份鉴别"],
        "itil_considerations": ["事件管理"],
    }
    compliance = {
        "compliance_status": "partial",
        "risk_level": "medium",
        "protection_level": "3",
        "missing_items": ["缺少审计日志"],
        "recommendations": ["启用集中审计"],
        "results": [{"module": "dengbao_2.0", "items": []}],
    }

    bundle = generate_document_bundle("doc-test", "implementation", solution, compliance)
    assert len(bundle.documents) == 7
    types = {d.doc_type for d in bundle.documents}
    assert "solution_summary" in types
    assert "remediation_plan" in types
    assert "remediation_record" in types
    assert "dengbao_record" in types
    assert "itil_incident" in types
    assert "change_request" in types


def test_document_agent_run():
    state = create_initial_state("doc-agent-001")
    state["last_solution"] = {
        "recommended_solution_id": "sol-a",
        "problem_analysis": "测试问题",
        "root_causes": ["根因1"],
        "solutions": [{"id": "sol-a", "title": "方案A", "description": "d", "approach": "a"}],
        "next_actions": ["执行"],
    }
    state["last_compliance_result"] = {
        "compliance_status": "partial",
        "risk_level": "medium",
        "protection_level": "3",
        "missing_items": [],
        "recommendations": [],
        "results": [],
    }

    result = DocumentAgent().run(state)
    assert len(result["generated_documents"]) == 7
    assert result["generated_documents"][0]["format"] == "markdown"


def test_should_generate_documents_partial():
    comp = {"compliance_status": "partial", "overall_status": "gaps_found", "risk_level": "medium"}
    assert is_partial_compliant(comp)
    assert should_generate_documents(comp)
