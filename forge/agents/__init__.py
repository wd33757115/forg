"""Forge specialist agents.

Import concrete agents from their modules, e.g. ``forge.agents.problem_solver``,
to avoid circular imports through this package ``__init__``.
"""

from forge.agents.output_base import AgentOutputBase

__all__ = ["AgentOutputBase"]
