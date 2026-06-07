"""Tests for AgentRegistry."""

from __future__ import annotations

import pytest

from forge.core.agent_registry import AgentRegistry, get_agent_registry, reset_agent_registry
from forge.core.state import create_initial_state


def test_register_and_get_node():
    registry = AgentRegistry()
    called = []

    def dummy_node(state):
        called.append(True)
        return {}

    registry.register("test_agent", dummy_node)
    fn = registry.get_node("test_agent")
    fn(create_initial_state("reg-test"))
    assert called
    assert registry.list_agents() == ["test_agent"]


def test_get_node_missing_raises():
    registry = AgentRegistry()
    with pytest.raises(KeyError, match="No agent node"):
        registry.get_node("missing")


def test_builtin_registry_has_six_agents_plus_pipeline():
    reset_agent_registry()
    registry = get_agent_registry()
    names = registry.list_agents()
    for name in (
        "problem_solver",
        "compliance",
        "security",
        "operations",
        "document",
        "pm_advisor",
        "execution",
        "approval_gate",
        "finalize",
    ):
        assert name in names
