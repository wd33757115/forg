"""Tests for Rule Pack loader."""

from forge.core.rule_pack import RulePackLoader, get_rule_pack


def test_list_available_modules():
    loader = RulePackLoader()
    modules = loader.list_available()
    assert "base_si" in modules
    assert "dengbao_2.0" in modules
    assert "itil_iso20000" in modules


def test_get_rule_pack_loads_all():
    packs = get_rule_pack()
    assert len(packs) == 3
    assert packs["dengbao_2.0"].rules[0].id.startswith("db-")


def test_rule_lookup():
    pack = get_rule_pack()["itil_iso20000"]
    rule = pack.get_rule("itil-inc-001")
    assert rule is not None
    assert rule.category == "incident"
