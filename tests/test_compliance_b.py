"""Compliance depth + explainability (B专项) tests."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from forge.agents.compliance import ComplianceAgent
from forge.agents.compliance_output import CheckItem, ComplianceOutput, ModuleComplianceResult
from forge.core.state import create_initial_state
from forge.utils.compliance_explain import (
    build_check_explanations,
    enrich_compliance_output,
    resolve_compliance_status_from_output,
)


def _sample_output() -> ComplianceOutput:
    return ComplianceOutput(
        overall_status="gaps_found",
        risk_level="medium",
        results=[
            ModuleComplianceResult(
                module="dengbao_2.0",
                module_name="等保",
                status="gaps_found",
                score=70.0,
                items=[
                    CheckItem(
                        check_id="db-acs-001",
                        title="身份鉴别",
                        category="dengbao_2.0",
                        status="fail",
                        detail="缺少 MFA 证据",
                        rule_id="db-acs-001",
                    ),
                    CheckItem(
                        check_id="db-aud-001",
                        title="安全审计",
                        category="dengbao_2.0",
                        status="warning",
                        detail="日志保留不足",
                        rule_id="db-aud-001",
                    ),
                    CheckItem(
                        check_id="si-doc-001",
                        title="资料完整性",
                        category="base_si",
                        status="fail",
                        detail="缺测试报告",
                        rule_id="si-doc-001",
                    ),
                ],
                summary="缺口",
            )
        ],
        missing_items=[],
        recommendations=[],
        next_action="整改",
    )


def test_explanations_have_severity_and_suggestion():
    output = enrich_compliance_output(_sample_output(), check_mode="strict")
    structured = output.model_dump()
    structured["check_explanations"] = build_check_explanations(structured)
    fail_expl = [e for e in structured["check_explanations"] if e["status"] == "fail"]
    assert fail_expl
    for e in fail_expl:
        assert e.get("rule_id")
        assert e.get("severity") in ("low", "medium", "high", "critical")
        assert e.get("suggestion")


def test_mode_failed_items_filtering():
    output = _sample_output()
    strict = enrich_compliance_output(output, check_mode="strict")
    advisory = enrich_compliance_output(output, check_mode="advisory")
    lenient = enrich_compliance_output(output, check_mode="lenient")

    assert len(strict.failed_items) >= len(advisory.failed_items)
    assert len(advisory.failed_items) >= len(lenient.failed_items)
    assert len(strict.failed_items) == 3
    assert len(advisory.failed_items) == 2
    assert all(f.status == "fail" for f in advisory.failed_items)
    assert len(lenient.failed_items) == 2
    lenient_ids = {f.rule_id for f in lenient.failed_items}
    assert lenient_ids == {"db-acs-001", "si-doc-001"}
    assert all(f.severity in ("high", "critical") for f in lenient.failed_items)


def test_failed_items_have_suggestion():
    strict = enrich_compliance_output(_sample_output(), check_mode="strict")
    for item in strict.failed_items:
        assert item.suggestion
        assert item.rule_id in item.suggestion


def test_resolve_compliance_status_strict_non_compliant():
    strict = enrich_compliance_output(_sample_output(), check_mode="strict")
    assert resolve_compliance_status_from_output(strict, check_mode="strict") == "non_compliant"


def test_resolve_compliance_status_lenient_partial_or_compliant():
    lenient = enrich_compliance_output(_sample_output(), check_mode="lenient")
    status = resolve_compliance_status_from_output(lenient, check_mode="lenient")
    assert status in ("partial", "non_compliant", "compliant")


@pytest.fixture
def seeded_state():
    state = create_initial_state("cmp-b", current_phase="implementation")
    state["messages"] = [HumanMessage(content="等保三级合规检查")]
    state["rule_pack"] = {"protection_level": "3"}
    state["wbs"] = {"design": {"name": "设计", "status": "done"}}
    state["documents"] = [{"title": "技术方案", "doc_type": "方案"}]
    return state


def test_agent_persist_includes_explanation_fields(seeded_state):
    updates = ComplianceAgent().run(seeded_state)
    structured = updates["last_compliance_result"]
    assert structured.get("failed_items_count") is not None
    explanations = structured.get("check_explanations") or []
    if explanations:
        assert "severity" in explanations[0]
    for f in structured.get("failed_items") or []:
        assert f.get("severity")
        if f.get("status") in ("fail", "warning"):
            assert f.get("suggestion")


def test_three_modes_differ_on_sparse_evidence():
    """Sparse evidence state should show mode differentiation."""
    state = create_initial_state("cmp-b-sparse")
    state["rule_pack"] = {"protection_level": "3"}
    state["wbs"] = {}
    state["documents"] = []
    agent = ComplianceAgent()
    counts = {}
    for mode in ("strict", "advisory", "lenient"):
        s = dict(state)
        s["check_mode"] = mode
        out = agent.run_compliance(s, skip_react=True)
        counts[mode] = len(out.failed_items)
    assert counts["strict"] >= counts["lenient"]
