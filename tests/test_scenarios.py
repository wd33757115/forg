"""Tests for CLI demo scenarios."""

from forge.cli.scenarios import get_scenario


def test_get_security_scenario():
    s = get_scenario("security")
    assert s is not None
    assert s.problem_type_hint == "security"


def test_get_itil_alias():
    s = get_scenario("operations")
    assert s is not None
    assert s.id == "itil"


def test_get_mixed_scenario():
    s = get_scenario("mixed")
    assert s is not None
    assert "401" in s.question or "故障" in s.question
