"""Central prompt loader — agents import prompts here instead of deep paths (decoupling)."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Final

_AGENT_PROMPT_MODULES: Final[dict[str, str]] = {
    "problem_solver": "forge.prompts.problem_solver.prompts",
    "compliance": "forge.prompts.compliance.prompts",
    "security": "forge.prompts.security.prompts",
    "operations": "forge.prompts.operations.prompts",
    "document": "forge.prompts.document.prompts",
    "pm_advisor": "forge.prompts.pm_advisor.prompts",
}

_cache: dict[str, ModuleType] = {}


def load_prompts(agent: str) -> ModuleType:
    """Load and cache the prompts module for an agent."""
    if agent not in _AGENT_PROMPT_MODULES:
        raise KeyError(f"No prompt module registered for agent '{agent}'")
    if agent not in _cache:
        _cache[agent] = importlib.import_module(_AGENT_PROMPT_MODULES[agent])
    return _cache[agent]


def clear_prompt_cache() -> None:
    """Clear loader cache (tests)."""
    _cache.clear()


def list_registered_agents() -> list[str]:
    return sorted(_AGENT_PROMPT_MODULES)
