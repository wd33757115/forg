"""Central tool registry — register and resolve Agent tools (net-ops style)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from forge.core.state import ProjectState

# Builder: ProjectState -> list of LangChain tools bound to that session
ToolBuilder = Callable[["ProjectState"], list[BaseTool]]


class ToolRegistry:
    """
    Registry mapping agent names to tool builder functions.

    Tools are state-bound callables recreated per invocation so they always
    see the current ProjectState snapshot.
    """

    def __init__(self) -> None:
        self._builders: dict[str, ToolBuilder] = {}

    def register(self, agent_name: str, builder: ToolBuilder) -> None:
        """Register a tool builder for an agent."""
        self._builders[agent_name] = builder

    def unregister(self, agent_name: str) -> None:
        self._builders.pop(agent_name, None)

    def has(self, agent_name: str) -> bool:
        return agent_name in self._builders

    def list_agents(self) -> list[str]:
        return sorted(self._builders)

    def get_tools(self, agent_name: str, state: "ProjectState") -> list[BaseTool]:
        """Build and return tools for the given agent and session state."""
        builder = self._builders.get(agent_name)
        if builder is None:
            raise KeyError(f"No tools registered for agent '{agent_name}'")
        return builder(state)


_registry: ToolRegistry | None = None


def _register_default_tools(registry: ToolRegistry) -> None:
    """Register built-in Forge agent tool sets (6 specialists)."""
    from forge.tools.compliance_tools import build_compliance_tools
    from forge.tools.document_tools import build_document_tools
    from forge.tools.operations_tools import build_operations_tools
    from forge.tools.pm_advisor_tools import build_pm_advisor_tools
    from forge.tools.problem_solver_tools import build_problem_solver_tools
    from forge.tools.security_tools import build_security_tools

    registry.register("problem_solver", build_problem_solver_tools)
    registry.register("compliance", build_compliance_tools)
    registry.register("security", build_security_tools)
    registry.register("operations", build_operations_tools)
    registry.register("document", build_document_tools)
    registry.register("pm_advisor", build_pm_advisor_tools)


def get_tool_registry() -> ToolRegistry:
    """Return the process-wide tool registry (lazy init with defaults)."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_default_tools(_registry)
    return _registry


def reset_tool_registry() -> None:
    """Clear registry (for tests)."""
    global _registry
    _registry = None
