"""Supervisor — routes work to the appropriate specialist agent."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from forge.core.rule_pack import DEFAULT_PACK_FILE, RulePack
from forge.core.rule_pack_loader import RulePackLoader
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

    On initialization loads the default Rule Pack (system_integration_v1.json)
    and injects it into project state on each invocation.
    Phase 2 will replace routing heuristics with LLM-based intent classification.
    """

    def __init__(self, rule_pack_path: str = DEFAULT_PACK_FILE) -> None:
        loader = RulePackLoader.get_instance()
        self.rule_pack: RulePack = loader.load(rule_pack_path)
        self._enabled_modules = self.rule_pack.get_enabled_modules()

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
            # Document intent before compliance — "等保材料" should route to document
            if any(kw in content for kw in ("文档", "document", "报告", "方案", "材料", "大纲")):
                return SupervisorDecision(
                    next_agent=AgentName.DOCUMENT,
                    reason="Message indicates document generation intent",
                )
            if any(kw in content for kw in ("等保", "合规", "compliance", "audit")):
                return SupervisorDecision(
                    next_agent=AgentName.COMPLIANCE,
                    reason="Message indicates compliance-related intent",
                )
            if any(kw in content for kw in ("问题", "故障", "problem", "incident", "根因")):
                return SupervisorDecision(
                    next_agent=AgentName.PROBLEM_SOLVER,
                    reason="Message indicates problem-solving intent",
                )

        return SupervisorDecision(
            next_agent=AgentName.END,
            reason="No pending tasks or recognizable intent; ending turn",
            confidence=0.5,
        )

    def _state_rule_pack_update(self, state: ProjectState) -> dict[str, Any]:
        """Build rule_pack state update, preserving project-specific enabled_modules."""
        pack_dict = self.rule_pack.to_state_dict()
        project_modules = state.get("enabled_modules")
        if project_modules:
            pack_dict["enabled_modules"] = project_modules
        return pack_dict

    def __call__(self, state: ProjectState) -> dict:
        """LangGraph node entrypoint."""
        decision = self.decide(state)
        return {
            "next_agent": decision.next_agent.value,
            "rule_pack": self._state_rule_pack_update(state),
            "enabled_modules": state.get("enabled_modules") or self._enabled_modules,
            "messages": [
                AIMessage(
                    content=(
                        f"[Supervisor] Rule Pack `{self.rule_pack.pack_id}` loaded | "
                        f"Routing to `{decision.next_agent}` — {decision.reason}"
                    ),
                    name="supervisor",
                )
            ],
        }
