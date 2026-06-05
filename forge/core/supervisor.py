"""Supervisor — routes work to the appropriate specialist agent."""

from __future__ import annotations

from enum import StrEnum

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from forge.core.state import ProjectState


class AgentName(StrEnum):
    """Known agents in the Forge graph (Phase 1 stubs + Phase 2 targets)."""

    SUPERVISOR = "supervisor"
    PROBLEM_SOLVER = "problem_solver"
    COMPLIANCE = "compliance"
    DOCUMENT = "document"
    END = "__end__"


class SupervisorDecision(BaseModel):
    """Structured routing decision from the Supervisor."""

    next_agent: AgentName
    reason: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class Supervisor:
    """
    Central routing node for the Forge agent graph.

    Phase 1 uses deterministic heuristics. Phase 2 will replace this with
    LLM-based intent classification over project context + messages.
    """

    def decide(self, state: ProjectState) -> SupervisorDecision:
        messages = state.get("messages", [])
        pending = state.get("pending_tasks", [])

        # Route based on open task assignment
        for task in pending:
            if task.get("status") != "open":
                continue
            assigned = task.get("assigned_to", "")
            if assigned == AgentName.COMPLIANCE:
                return SupervisorDecision(
                    next_agent=AgentName.COMPLIANCE,
                    reason=f"Open compliance task: {task.get('title', '')}",
                )
            if assigned == AgentName.DOCUMENT:
                return SupervisorDecision(
                    next_agent=AgentName.DOCUMENT,
                    reason=f"Open document task: {task.get('title', '')}",
                )
            if assigned == AgentName.PROBLEM_SOLVER:
                return SupervisorDecision(
                    next_agent=AgentName.PROBLEM_SOLVER,
                    reason=f"Open problem-solving task: {task.get('title', '')}",
                )

        # Route based on latest user message keywords (simple heuristic)
        if messages:
            last = messages[-1]
            content = getattr(last, "content", str(last)).lower()
            if any(kw in content for kw in ("等保", "合规", "compliance", "audit")):
                return SupervisorDecision(
                    next_agent=AgentName.COMPLIANCE,
                    reason="Message indicates compliance-related intent",
                )
            if any(kw in content for kw in ("文档", "document", "报告", "方案")):
                return SupervisorDecision(
                    next_agent=AgentName.DOCUMENT,
                    reason="Message indicates document generation intent",
                )
            if any(kw in content for kw in ("问题", "故障", "problem", "incident", "根因")):
                return SupervisorDecision(
                    next_agent=AgentName.PROBLEM_SOLVER,
                    reason="Message indicates problem-solving intent",
                )

        # Default: end turn when no clear routing signal
        return SupervisorDecision(
            next_agent=AgentName.END,
            reason="No pending tasks or recognizable intent; ending turn",
            confidence=0.5,
        )

    def __call__(self, state: ProjectState) -> dict:
        """LangGraph node entrypoint."""
        decision = self.decide(state)
        return {
            "next_agent": decision.next_agent.value,
            "messages": [
                AIMessage(
                    content=f"[Supervisor] Routing to `{decision.next_agent}` — {decision.reason}",
                    name="supervisor",
                )
            ],
        }
