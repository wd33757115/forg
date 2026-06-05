"""Supervisor — orchestrates ProblemSolver ↔ Compliance closed-loop workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from forge.core.rule_pack import DEFAULT_PACK_FILE, RulePack
from forge.core.rule_pack_loader import RulePackLoader
from forge.core.state import WORKFLOW_PROBLEM_COMPLIANCE_LOOP, ProjectState

# Maximum compliance-driven re-optimizations of the solution (after the first attempt)
MAX_COMPLIANCE_RETRIES = 2


class AgentName(StrEnum):
    """Known agents and workflow nodes in the Forge graph."""

    SUPERVISOR = "supervisor"
    PROBLEM_SOLVER = "problem_solver"
    COMPLIANCE = "compliance"
    DOCUMENT = "document"
    FINALIZE = "finalize"
    END = "__end__"


class WorkflowStep(StrEnum):
    """Supervisor routing phase within a session."""

    INITIAL = "initial"
    RETRY = "retry"
    POST_COMPLIANCE = "post_compliance"


class SupervisorDecision(BaseModel):
    """Structured routing decision from the Supervisor."""

    next_agent: AgentName
    reason: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


def is_compliant(compliance_result: dict[str, Any] | None) -> bool:
    """Return True when compliance_status is compliant or overall_status is pass."""
    if not compliance_result:
        return False
    if compliance_result.get("compliance_status") == "compliant":
        return True
    return compliance_result.get("overall_status") == "pass"


def is_non_compliant(compliance_result: dict[str, Any] | None) -> bool:
    return not is_compliant(compliance_result)


class Supervisor:
    """
    Central orchestrator for the Forge agent graph.

    Closed-loop flow (problem-solving queries):
        Supervisor → ProblemSolver → Compliance → (retry Supervisor → ProblemSolver)* → Finalize

    Standalone flows (document / audit-only queries) route to a single specialist.
    """

    def __init__(self, rule_pack_path: str = DEFAULT_PACK_FILE) -> None:
        loader = RulePackLoader.get_instance()
        self.rule_pack: RulePack = loader.load(rule_pack_path)
        self._enabled_modules = self.rule_pack.get_enabled_modules()

    def _state_rule_pack_update(self, state: ProjectState) -> dict[str, Any]:
        pack_dict = self.rule_pack.to_state_dict()
        project_modules = state.get("enabled_modules")
        if project_modules:
            pack_dict["enabled_modules"] = project_modules
        return pack_dict

    def _is_problem_intent(self, content: str) -> bool:
        problem_keywords = (
            "问题",
            "故障",
            "problem",
            "incident",
            "根因",
            "异常",
            "报错",
            "error",
            "失败",
            "宕机",
            "超时",
            "诊断",
        )
        return any(kw in content for kw in problem_keywords)

    def _is_document_intent(self, content: str) -> bool:
        return any(kw in content for kw in ("文档", "document", "报告", "方案", "材料", "大纲"))

    def _is_compliance_only_intent(self, content: str) -> bool:
        """Pure compliance audit without problem-solving (no closed loop)."""
        compliance_keywords = (
            "等保",
            "合规",
            "compliance",
            "audit",
            "测评",
            "整改",
            "缺口",
            "gap",
            "扫描",
            "检查",
            "审计",
            "dengbao",
        )
        return any(kw in content for kw in compliance_keywords)

    def decide_initial(self, state: ProjectState) -> SupervisorDecision:
        """Route a new user request to the appropriate entry agent."""
        messages = state.get("messages", [])
        pending = state.get("pending_tasks", [])

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

        if messages:
            content = getattr(messages[-1], "content", str(messages[-1])).lower()

            if self._is_document_intent(content):
                return SupervisorDecision(
                    next_agent=AgentName.DOCUMENT,
                    reason="Document generation intent",
                )

            # Problem + compliance keywords → closed loop starting at ProblemSolver
            if self._is_problem_intent(content):
                return SupervisorDecision(
                    next_agent=AgentName.PROBLEM_SOLVER,
                    reason="Problem-solving closed loop: ProblemSolver → Compliance",
                )

            if self._is_compliance_only_intent(content):
                return SupervisorDecision(
                    next_agent=AgentName.COMPLIANCE,
                    reason="Standalone compliance audit",
                )

        return SupervisorDecision(
            next_agent=AgentName.END,
            reason="No recognizable intent",
            confidence=0.5,
        )

    def decide_after_compliance(self, state: ProjectState) -> SupervisorDecision:
        """
        After ComplianceAgent runs in the closed loop, decide retry or finalize.

        Retries up to MAX_COMPLIANCE_RETRIES when non_compliant.
        """
        compliance = state.get("last_compliance_result") or {}
        retry_count = state.get("compliance_retry_count", 0)

        if is_compliant(compliance):
            return SupervisorDecision(
                next_agent=AgentName.FINALIZE,
                reason="Solution is compliant — finalizing output",
                confidence=1.0,
            )

        if retry_count < MAX_COMPLIANCE_RETRIES:
            return SupervisorDecision(
                next_agent=AgentName.PROBLEM_SOLVER,
                reason=(
                    f"non_compliant — re-optimizing solution "
                    f"(retry {retry_count + 1}/{MAX_COMPLIANCE_RETRIES})"
                ),
            )

        return SupervisorDecision(
            next_agent=AgentName.FINALIZE,
            reason=(
                f"non_compliant after {retry_count} retries — "
                "finalizing with best effort + compliance gaps"
            ),
            confidence=0.6,
        )

    def _build_retry_feedback_message(self, compliance: dict[str, Any]) -> HumanMessage:
        """Inject compliance gaps as context for ProblemSolver re-optimization."""
        missing = compliance.get("missing_items", [])
        recs = compliance.get("recommendations", [])
        body = (
            "【合规反馈 — 请优化方案】\n"
            f"合规状态: {compliance.get('compliance_status', 'non_compliant')}\n"
            f"风险等级: {compliance.get('risk_level', 'unknown')}\n\n"
            "缺失项:\n"
            + ("\n".join(f"- {m}" for m in missing[:8]) if missing else "- 见上次合规报告")
            + "\n\n整改建议:\n"
            + ("\n".join(f"- {r}" for r in recs[:5]) if recs else "- 请对照 Rule Pack 补齐证据")
            + "\n\n请基于以上合规反馈重新生成更合规的解决方案。"
        )
        return HumanMessage(content=body)

    def __call__(self, state: ProjectState) -> dict[str, Any]:
        """LangGraph supervisor node — handles initial routing and retry orchestration."""
        step = state.get("workflow_step") or WorkflowStep.INITIAL

        if step == WorkflowStep.POST_COMPLIANCE:
            decision = self.decide_after_compliance(state)
        elif step == WorkflowStep.RETRY:
            # Entering retry: increment counter and inject feedback
            compliance = state.get("last_compliance_result") or {}
            retry_count = state.get("compliance_retry_count", 0) + 1
            return {
                "next_agent": AgentName.PROBLEM_SOLVER.value,
                "compliance_retry_count": retry_count,
                "workflow_step": WorkflowStep.INITIAL,
                "active_workflow": WORKFLOW_PROBLEM_COMPLIANCE_LOOP,
                "rule_pack": self._state_rule_pack_update(state),
                "messages": [
                    AIMessage(
                        content=(
                            f"[Supervisor] Compliance retry {retry_count}/{MAX_COMPLIANCE_RETRIES} "
                            "— sending feedback to ProblemSolver"
                        ),
                        name="supervisor",
                    ),
                    self._build_retry_feedback_message(compliance),
                ],
            }
        else:
            decision = self.decide_initial(state)

        updates: dict[str, Any] = {
            "next_agent": decision.next_agent.value,
            "rule_pack": self._state_rule_pack_update(state),
            "enabled_modules": state.get("enabled_modules") or self._enabled_modules,
            "messages": [
                AIMessage(
                    content=(
                        f"[Supervisor] Rule Pack `{self.rule_pack.pack_id}` | "
                        f"→ `{decision.next_agent}` — {decision.reason}"
                    ),
                    name="supervisor",
                )
            ],
        }

        # Start closed loop for problem-solving entry
        last_content = ""
        if messages := state.get("messages"):
            last_content = str(getattr(messages[-1], "content", messages[-1])).lower()
        if (
            step == WorkflowStep.INITIAL
            and decision.next_agent == AgentName.PROBLEM_SOLVER
            and self._is_problem_intent(last_content)
        ):
            updates["active_workflow"] = WORKFLOW_PROBLEM_COMPLIANCE_LOOP
            updates["compliance_retry_count"] = 0
            updates["last_solution"] = None
            updates["last_compliance_result"] = None

        return updates


# ---------------------------------------------------------------------------
# LangGraph conditional edge routers (imported by workflow.py)
# ---------------------------------------------------------------------------


def route_after_supervisor(state: ProjectState) -> str:
    """Map supervisor next_agent to graph node."""
    next_agent = state.get("next_agent")
    if next_agent == AgentName.PROBLEM_SOLVER:
        return AgentName.PROBLEM_SOLVER
    if next_agent == AgentName.COMPLIANCE:
        return AgentName.COMPLIANCE
    if next_agent == AgentName.DOCUMENT:
        return AgentName.DOCUMENT
    if next_agent == AgentName.FINALIZE:
        return AgentName.FINALIZE
    return AgentName.END


def route_after_problem_solver(state: ProjectState) -> str:
    """In closed loop, always proceed to Compliance after ProblemSolver."""
    if state.get("active_workflow") == WORKFLOW_PROBLEM_COMPLIANCE_LOOP:
        return AgentName.COMPLIANCE
    return AgentName.END


def route_after_compliance(state: ProjectState) -> str:
    """
    After Compliance in closed loop → supervisor post-compliance routing.
    Standalone compliance audit → finalize directly.
    """
    if state.get("active_workflow") == WORKFLOW_PROBLEM_COMPLIANCE_LOOP:
        return AgentName.SUPERVISOR

    return AgentName.FINALIZE


def supervisor_post_compliance_node(state: ProjectState) -> dict[str, Any]:
    """
    Wrapper node: set workflow_step=post_compliance then run supervisor logic.

    Separated so the graph can route compliance → supervisor → problem_solver|finalize.
    """
    state_with_step = {**state, "workflow_step": WorkflowStep.POST_COMPLIANCE}
    supervisor = Supervisor()
    result = supervisor(state_with_step)

    # If supervisor decides to retry, route through retry step on next supervisor call
    if result.get("next_agent") == AgentName.PROBLEM_SOLVER.value:
        retry_state = {**state, **result, "workflow_step": WorkflowStep.RETRY}
        return Supervisor()(retry_state)

    return result


def finalize_node(state: ProjectState) -> dict[str, Any]:
    """Emit final combined output: ProblemSolver solution + Compliance result."""
    solution = state.get("last_solution") or {}
    compliance = state.get("last_compliance_result") or {}
    retry_count = state.get("compliance_retry_count", 0)

    rec_id = solution.get("recommended_solution_id", "N/A")
    analysis = solution.get("problem_analysis", "无方案输出")
    comp_status = compliance.get("compliance_status", compliance.get("overall_status", "unknown"))
    risk = compliance.get("risk_level", "unknown")
    missing = compliance.get("missing_items", [])
    next_action = compliance.get("next_action", "")

    lines = [
        "# Forge 闭环执行结果",
        "",
        f"**合规重试次数**: {retry_count}",
        f"**最终合规状态**: {comp_status}",
        f"**风险等级**: {risk}",
        "",
        "## ProblemSolver 推荐方案",
        f"方案 ID: `{rec_id}`",
        "",
        analysis,
        "",
        "## Compliance 检查结果",
    ]

    if compliance.get("results"):
        for mod in compliance["results"]:
            lines.append(f"- **{mod.get('module_name', mod.get('module'))}**: "
                         f"{mod.get('status')} (score {mod.get('score')})")
    else:
        lines.append(f"- 状态: {compliance.get('overall_status', 'N/A')}")

    if missing:
        lines.extend(["", "## 合规缺口", *[f"- {m}" for m in missing[:10]]])

    if compliance.get("recommendations"):
        lines.extend(["", "## 整改建议", *[f"- {r}" for r in compliance["recommendations"][:5]]])

    if next_action:
        lines.extend(["", "## 下一步行动", next_action])

    # Structured JSON appendix
    if solution:
        lines.extend(["", "## 方案 JSON", f"```json\n{_safe_json(solution)}\n```"])

    return {
        "next_agent": AgentName.END.value,
        "workflow_step": None,
        "active_workflow": None,
        "messages": [AIMessage(content="\n".join(lines), name="forge_finalize")],
    }


def _safe_json(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2)[:4000]
