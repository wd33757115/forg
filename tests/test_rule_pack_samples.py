"""Tests for sample Rule Pack JSON files."""

from forge.core.rule_pack import RulePack


def test_system_integration_has_enriched_rules():
    pack = RulePack.load_rule_pack("system_integration_v1.json")
    assert len(pack.get_module("base_si").rules) >= 10
    dengbao = pack.get_module("dengbao_2.0")
    assert len(dengbao.rules) >= 15
    categories = {r.category for r in dengbao.rules}
    assert "host_security" in categories
    assert "network" in categories
    assert "application" in categories
    assert "data_security" in categories
    assert "management" in categories
    assert len(pack.get_module("itil_iso20000").rules) >= 10


def test_dengbao_level3_sample():
    pack = RulePack.load_rule_pack("dengbao_level3_sample.json")
    mod = pack.get_module("dengbao_2.0")
    assert mod is not None
    assert len(mod.rules) >= 5
    assert any("身份鉴别" in r.title for r in mod.rules)


def test_itil_basic_sample():
    pack = RulePack.load_rule_pack("itil_basic_sample.json")
    mod = pack.get_module("itil_iso20000")
    assert mod is not None
    assert len(mod.rules) >= 5
    assert any(r.category == "incident" for r in mod.rules)
