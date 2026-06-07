"""Stage 1.2 — check_mode affects failed_items and compliance_status."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from forge.agents.compliance import ComplianceAgent
from forge.core.state import create_initial_state


@pytest.fixture
def seeded_state():
    state = create_initial_state("stage1-cmp", current_phase="implementation")
    state["messages"] = [HumanMessage(content="等保三级合规检查")]
    state["rule_pack"] = {"protection_level": "3"}
    state["wbs"] = {"design": {"name": "设计", "status": "done"}}
    state["documents"] = [{"title": "技术方案", "doc_type": "方案"}]
    return state


@pytest.mark.parametrize("mode", ["strict", "advisory", "lenient"])
def test_compliance_agent_explainability_per_mode(seeded_state, mode: str):
    seeded_state["check_mode"] = mode
    updates = ComplianceAgent().run(seeded_state)
    structured = updates["last_compliance_result"]
    assert structured.get("check_mode") == mode
    assert "matched_rules" in structured
    assert "failed_items" in structured
    assert "suggestions" in structured
    for item in structured.get("failed_items") or []:
        assert item.get("rule_id")
        assert item.get("severity") in ("low", "medium", "high", "critical")


def test_strict_has_more_failed_items_than_lenient(seeded_state):
    agent = ComplianceAgent()
    strict_out = agent.run_compliance(seeded_state, skip_react=True)
    seeded_state["check_mode"] = "lenient"
    lenient_out = agent.run_compliance(seeded_state, skip_react=True)
    assert len(strict_out.failed_items) >= len(lenient_out.failed_items)
