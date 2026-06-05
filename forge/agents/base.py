"""Base agent interface for Forge specialists."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import AIMessage

from forge.agents.output_base import AgentOutputBase
from forge.core.state import ProjectState
from forge.utils.logger import get_logger


class BaseAgent(ABC):
    """Common contract for all Forge agents."""

    name: str = "base"

    @abstractmethod
    def run(self, state: ProjectState) -> dict[str, Any]:
        """Execute agent logic and return state updates."""

    def __call__(self, state: ProjectState) -> dict[str, Any]:
        """LangGraph node entry — prefer workflow ``wrap_agent_node`` for error recovery."""
        logger = get_logger(self.name)
        run_id = state.get("run_id", "?")
        logger.info("[%s] agent=%s invoke", run_id, self.name)
        try:
            return self.run(state)
        except Exception:
            logger.exception("[%s] agent=%s unhandled error", run_id, self.name)
            raise

    def reply(self, content: str) -> dict[str, Any]:
        return {"messages": [AIMessage(content=content, name=self.name)]}

    def structured_update(
        self,
        output: AgentOutputBase,
        *,
        state_key: str,
    ) -> dict[str, Any]:
        """Standard state write for a Pydantic agent output model."""
        return {state_key: output.to_state_dict()}
