"""Tests for central prompt loader (agent decoupling)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from forge.prompts.loader import clear_prompt_cache, list_registered_agents, load_prompts

ROOT = Path(__file__).resolve().parents[1]
AGENT_FILES = [
    "forge/agents/problem_solver.py",
    "forge/agents/compliance.py",
    "forge/agents/security.py",
    "forge/agents/operations.py",
    "forge/agents/document.py",
    "forge/agents/pm_advisor.py",
]


def _imports_deep_prompts(path: Path) -> list[str]:
    """Detect direct imports of forge.prompts.<agent>.prompts (bypass loader)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("forge.prompts.") and node.module.endswith(".prompts"):
                hits.append(node.module)
            if node.module.endswith("_prompt"):
                hits.append(node.module)
    return hits


@pytest.mark.parametrize("agent", list_registered_agents())
def test_load_prompts_returns_module(agent: str):
    clear_prompt_cache()
    mod = load_prompts(agent)
    assert mod is not None
    assert hasattr(mod, "__file__")


@pytest.mark.parametrize("rel_path", AGENT_FILES)
def test_agents_use_loader_not_deep_prompt_paths(rel_path: str):
    path = ROOT / rel_path
    assert not _imports_deep_prompts(path), f"{rel_path} imports prompts directly"
