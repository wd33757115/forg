"""Base agent interface for Forge specialists."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import AIMessage

from forge.core.state import ProjectState


class BaseAgent(ABC):
    """Common contract for all Forge agents."""

    name: str = "base"

    @abstractmethod
    def run(self, state: ProjectState) -> dict[str, Any]:
        """Execute agent logic and return state updates."""

    def __call__(self, state: ProjectState) -> dict[str, Any]:
        return self.run(state)

    def reply(self, content: str) -> dict[str, Any]:
        return {"messages": [AIMessage(content=content, name=self.name)]}
