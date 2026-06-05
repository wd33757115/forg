"""Tests for Rule Pack loader."""

import pytest

from forge.core.rule_pack import DEFAULT_PACK_FILE, RulePack
from forge.core.rule_pack_loader import RulePackLoader, get_rule_pack


@pytest.fixture(autouse=True)
def _reset_loader():
    RulePackLoader.reset_instance()
    yield
    RulePackLoader.reset_instance()


def test_list_available_packs():
    loader = RulePackLoader.get_instance()
    packs = loader.list_available()
    assert DEFAULT_PACK_FILE in packs


def test_load_rule_pack_bundle():
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    assert pack.pack_id == "system_integration_v1"
    assert len(pack.get_enabled_modules()) == 3


def test_get_enabled_modules():
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    modules = pack.get_enabled_modules()
    assert "base_si" in modules
    assert "dengbao_2.0" in modules
    assert "itil_iso20000" in modules


def test_validate_module():
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    assert pack.validate_module("base_si") is True
    assert pack.validate_module("nonexistent") is False


def test_get_module():
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    module = pack.get_module("dengbao_2.0")
    assert module is not None
    assert module.rules[0].id.startswith("db-")


def test_get_rule_pack_returns_module_map():
    modules = get_rule_pack()
    assert len(modules) == 3
    assert modules["itil_iso20000"].get_rule("itil-inc-001") is not None


def test_loader_singleton_cache():
    loader = RulePackLoader.get_instance()
    a = loader.load(DEFAULT_PACK_FILE)
    b = loader.load(DEFAULT_PACK_FILE)
    assert a is b


def test_rule_lookup_by_category():
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    module = pack.get_module("itil_iso20000")
    assert module is not None
    incident_rules = module.rules_by_category("incident")
    assert len(incident_rules) >= 1
    assert incident_rules[0].category == "incident"
