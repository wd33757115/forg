"""BaseAgent — unified contract for all Forge specialist agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence, TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from forge.agents.output_base import AgentOutputBase
from forge.core.state import ProjectState
from forge.core.tool_registry import get_tool_registry
from forge.utils.llm import (
    get_llm,
    invoke_llm,
    invoke_react_agent,
    invoke_structured_output,
    invoke_with_retry,
)
from forge.utils.logger import get_logger

T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC):
    """
    Abstract base for Forge agents (net-ops inspired).

    Subclasses implement ``run(state)``; the base class provides:
    - Unified logging and ``__call__`` entry
    - Tool resolution via ``ToolRegistry``
    - LLM helpers (text, structured, ReAct)
    - Standard message / state update helpers
    """

    name: str = "base"

    def __init__(self) -> None:
        self._logger = get_logger(self.name)

    @property
    def logger(self):
        return self._logger

    @abstractmethod
    def run(self, state: ProjectState) -> dict[str, Any]:
        """Execute agent logic and return LangGraph state updates."""

    def __call__(self, state: ProjectState) -> dict[str, Any]:
        """LangGraph node entry — errors propagate to ``wrap_agent_node``."""
        run_id = state.get("run_id", "?")
        self.logger.info("[%s] agent=%s invoke", run_id, self.name)
        try:
            return self.run(state)
        except Exception:
            self.logger.exception("[%s] agent=%s unhandled error", run_id, self.name)
            raise

    # ------------------------------------------------------------------
    # Tools (ToolRegistry)
    # ------------------------------------------------------------------

    def get_tools(self, state: ProjectState):
        """Resolve tools registered for this agent."""
        return get_tool_registry().get_tools(self.name, state)

    # ------------------------------------------------------------------
    # LLM helpers (utils/llm.py)
    # ------------------------------------------------------------------

    def llm_available(self) -> bool:
        return get_llm() is not None

    def invoke_text(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
    ) -> str | None:
        return invoke_llm(system, user, temperature=temperature)

    def invoke_structured(
        self,
        schema: type[T],
        messages: Sequence[BaseMessage],
        *,
        temperature: float | None = None,
    ) -> T | None:
        return invoke_structured_output(schema, messages, temperature=temperature)

    def run_react(
        self,
        state: ProjectState,
        *,
        system: str,
        task: str,
        temperature: float = 0.2,
        fallback: str = "",
    ) -> str:
        """
        Run a ReAct loop with this agent's registered tools.

        Returns research text, or ``fallback`` when LLM unavailable / on error.
        """
        llm = get_llm(temperature=temperature)
        if llm is None:
            self.logger.debug("ReAct skipped — no LLM; using fallback")
            return fallback

        tools = self.get_tools(state)
        react_agent = create_react_agent(llm, tools)
        try:
            result = invoke_react_agent(
                react_agent,
                {
                    "messages": [
                        SystemMessage(content=system),
                        HumanMessage(content=task),
                    ]
                },
            )
            final_messages = result.get("messages", [])
            if final_messages:
                return str(getattr(final_messages[-1], "content", final_messages[-1]))
        except Exception as exc:
            self.logger.warning("ReAct failed for %s: %s", self.name, exc)
        return fallback

    def invoke_messages(
        self,
        messages: Sequence[BaseMessage],
        *,
        temperature: float | None = None,
    ) -> str | None:
        """Low-level chat invoke with retry."""
        llm = get_llm(temperature=temperature)
        if llm is None:
            return None
        try:
            response = invoke_with_retry(llm, messages)
            return str(response.content)
        except Exception as exc:
            self.logger.warning("invoke_messages failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def reply(self, content: str) -> dict[str, Any]:
        return {"messages": [AIMessage(content=content, name=self.name)]}

    def structured_update(
        self,
        output: AgentOutputBase,
        *,
        state_key: str,
    ) -> dict[str, Any]:
        return {state_key: output.to_state_dict()}
