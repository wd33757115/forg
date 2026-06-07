"""Tests for ensure_minimum_references in rule_pack_refs."""

from __future__ import annotations

from forge.agents.rule_pack_refs import ensure_minimum_references


def test_ensure_minimum_references_pads_to_three():
    refs = ensure_minimum_references([], "security", "等保三级登录401认证失败", minimum=3)
    assert len(refs) >= 3
    assert all(r.rule_id for r in refs)


def test_ensure_minimum_references_preserves_existing():
    from forge.agents.solution_output import RulePackReference

    existing = [
        RulePackReference(
            rule_id="db-acs-001",
            module="dengbao_2.0",
            title="身份鉴别",
            relevance="test",
        )
    ]
    refs = ensure_minimum_references(existing, "security", "登录401", minimum=3)
    assert refs[0].rule_id == "db-acs-001"
    assert len(refs) >= 3
