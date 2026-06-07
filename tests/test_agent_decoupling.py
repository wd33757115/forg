"""Ensure agents resolve tools via ToolRegistry, not direct build_*_tools imports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from forge.core import create_initial_state
from forge.core.tool_registry import get_tool_registry

AGENT_FILES = [
    "forge/agents/problem_solver.py",
    "forge/agents/compliance.py",
    "forge/agents/security.py",
    "forge/agents/operations.py",
    "forge/agents/document.py",
    "forge/agents/pm_advisor.py",
]

ROOT = Path(__file__).resolve().parents[1]


def _imports_build_tools(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name.startswith("build_") and alias.name.endswith("_tools"):
                    hits.append(f"{node.module}.{alias.name}")
    return hits


@pytest.mark.parametrize("rel_path", AGENT_FILES)
def test_agents_do_not_import_build_tools(rel_path: str):
    """Agents must use BaseAgent.get_tools / ToolRegistry, not build_*_tools."""
    path = ROOT / rel_path
    assert not _imports_build_tools(path), f"{rel_path} imports build_*_tools directly"


@pytest.mark.parametrize(
    "agent_name",
    ["problem_solver", "compliance", "security", "operations", "document", "pm_advisor"],
)
def test_all_agents_registered_in_registry(agent_name: str):
    state = create_initial_state(f"decouple-{agent_name}")
    tools = get_tool_registry().get_tools(agent_name, state)
    assert tools, f"{agent_name} has no tools"
