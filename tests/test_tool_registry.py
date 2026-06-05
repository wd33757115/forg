"""Tests for central ToolRegistry."""

from __future__ import annotations

import pytest
from langchain_core.tools import tool

from forge.core import create_initial_state
from forge.core.tool_registry import ToolRegistry, get_tool_registry, reset_tool_registry

EXPECTED_AGENTS = (
    "problem_solver",
    "compliance",
    "security",
    "operations",
    "document",
    "pm_advisor",
)


@tool
def dummy_tool(query: str) -> str:
    """Echo query for tests."""
    return query


def _builder(state):
    return [dummy_tool]


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_tool_registry()
    yield
    reset_tool_registry()


def test_default_registry_has_all_six_agents():
    registry = get_tool_registry()
    assert registry.list_agents() == sorted(EXPECTED_AGENTS)
    for name in EXPECTED_AGENTS:
        assert registry.has(name)


def test_default_registry_tool_names():
    registry = get_tool_registry()
    state = create_initial_state("tool-reg-test")
    ps_tools = {t.name for t in registry.get_tools("problem_solver", state)}
    assert "query_rule_pack" in ps_tools
    doc_tools = {t.name for t in registry.get_tools("document", state)}
    assert "list_document_templates" in doc_tools
    sec_tools = registry.get_tools("security", state)
    assert sec_tools


def test_register_and_get_custom_agent():
    registry = ToolRegistry()
    registry.register("custom", _builder)
    state = create_initial_state("custom-agent")
    tools = registry.get_tools("custom", state)
    assert len(tools) == 1
    assert tools[0].name == "dummy_tool"


def test_get_tools_unknown_agent_raises():
    registry = ToolRegistry()
    state = create_initial_state("missing")
    with pytest.raises(KeyError, match="No tools registered"):
        registry.get_tools("nonexistent", state)
