"""Lightweight AgentRegistry — register agent nodes for workflow composition."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from forge.core.state import ProjectState

AgentNodeFn = Callable[[ProjectState], dict[str, Any]]


class AgentRegistry:
    """Maps agent names to LangGraph node callables (optionally wrapped)."""

    def __init__(self) -> None:
        self._nodes: dict[str, AgentNodeFn] = {}

    def register(self, name: str, node_fn: AgentNodeFn) -> None:
        self._nodes[name] = node_fn

    def unregister(self, name: str) -> None:
        self._nodes.pop(name, None)

    def get_node(self, name: str) -> AgentNodeFn:
        if name not in self._nodes:
            raise KeyError(f"No agent node registered for '{name}'")
        return self._nodes[name]

    def has(self, name: str) -> bool:
        return name in self._nodes

    def list_agents(self) -> list[str]:
        return sorted(self._nodes)


_registry: AgentRegistry | None = None


def _register_builtin_agents(registry: AgentRegistry) -> None:
    from forge.agents.compliance import compliance_node
    from forge.agents.document import document_node
    from forge.agents.operations import operations_node
    from forge.agents.pm_advisor import pm_advisor_node
    from forge.agents.problem_solver import problem_solver_node
    from forge.agents.security import security_node
    from forge.core.approval.node import approval_gate_node
    from forge.core.execution.node import execution_node
    from forge.core.supervisor import finalize_node
    from forge.utils.agent_runner import wrap_agent_node

    optional = {"security", "operations", "document", "pm_advisor"}
    for name, fn in (
        ("problem_solver", problem_solver_node),
        ("compliance", compliance_node),
        ("security", security_node),
        ("operations", operations_node),
        ("document", document_node),
        ("pm_advisor", pm_advisor_node),
    ):
        registry.register(
            name,
            wrap_agent_node(fn, name, optional=name in optional),
        )
    registry.register("execution", execution_node)
    registry.register("approval_gate", approval_gate_node)
    registry.register("finalize", finalize_node)


def get_agent_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
        _register_builtin_agents(_registry)
    return _registry


def reset_agent_registry() -> None:
    global _registry
    _registry = None
