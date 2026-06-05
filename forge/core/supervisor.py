"""Supervisor — orchestrates ProblemSolver ↔ Compliance closed-loop workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from forge.core.pipeline import PipelinePlanner
from forge.core.rule_pack import DEFAULT_PACK_FILE, RulePack
from forge.core.rule_pack_loader import RulePackLoader
from forge.core.state import (
    WORKFLOW_OPERATIONS_STANDALONE,
    WORKFLOW_PROBLEM_COMPLIANCE_LOOP,
    WORKFLOW_SECURITY_STANDALONE,
    ProjectState,
)
from forge.utils.conversation import record_conversation, record_thinking
from forge.utils.logger import get_logger, log_pipeline_step

logger = get_logger("supervisor")

# Maximum compliance-driven re-optimizations of the solution (after the first attempt)
MAX_COMPLIANCE_RETRIES = 2


class AgentName(StrEnum):
    """Known agents and workflow nodes in the Forge graph."""

    SUPERVISOR = "supervisor"
    PROBLEM_SOLVER = "problem_solver"
    COMPLIANCE = "compliance"
    SECURITY = "security"
    OPERATIONS = "operations"
    DOCUMENT = "document"
    PM_ADVISOR = "pm_advisor"
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


def is_partial_compliant(compliance_result: dict[str, Any] | None) -> bool:
    """Return True when compliance is partial (gaps but manageable risk)."""
    if not compliance_result:
        return False
    if compliance_result.get("compliance_status") == "partial":
        return True
    return (
        compliance_result.get("overall_status") == "gaps_found"
        and compliance_result.get("risk_level") in ("low", "medium")
    )


def should_generate_documents(compliance_result: dict[str, Any] | None) -> bool:
    """DocumentAgent runs when compliant or partial."""
    return is_compliant(compliance_result) or is_partial_compliant(compliance_result)


def is_non_compliant(compliance_result: dict[str, Any] | None) -> bool:
    """Fully non-compliant — not eligible for document generation."""
    if not compliance_result:
        return True
    status = compliance_result.get("compliance_status")
    if status == "non_compliant":
        return True
    return not is_compliant(compliance_result) and not is_partial_compliant(compliance_result)


class Supervisor:
    """
    Central orchestrator for the Forge agent graph.

    Closed-loop flow (problem-solving queries):
        Supervisor → ProblemSolver → (Security|Operations)* → Compliance
            → (retry)* → Document → PMAdvisor → Finalize

    Specialist routing uses specialist_queue (security / operations) after ProblemSolver.
    Standalone Security/Operations/Compliance flows route to a single entry specialist.
    """

    def __init__(self, rule_pack_path: str = DEFAULT_PACK_FILE) -> None:
        loader = RulePackLoader.get_instance()
        self.rule_pack: RulePack = loader.load(rule_pack_path)
        self._enabled_modules = self.rule_pack.get_enabled_modules()
        self._planner = PipelinePlanner()

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

    def _is_security_intent(self, content: str) -> bool:
        """等保 / 安全 / 测评相关意图 — 优先 SecurityAgent。"""
        security_keywords = (
            "等保",
            "安全",
            "测评",
            "dengbao",
            "security",
            "防火墙",
            "审计",
            "访问控制",
            "渗透",
            "漏洞",
            "加固",
            "边界",
        )
        return any(kw in content for kw in security_keywords)

    def _is_operations_intent(self, content: str) -> bool:
        """ITIL / 事件 / 变更相关意图 — 优先 OperationsAgent。"""
        operations_keywords = (
            "事件",
            "问题管理",
            "sla",
            "变更",
            "itil",
            "incident",
            "problem",
            "cmdb",
            "服务台",
            "工单",
            "cab",
            "服务级别",
        )
        return any(kw in content for kw in operations_keywords)

    def _is_compliance_only_intent(self, content: str) -> bool:
        """Pure compliance audit without problem-solving (no closed loop)."""
        compliance_keywords = (
            "合规",
            "compliance",
            "audit",
            "缺口",
            "gap",
            "扫描",
            "检查",
        )
        return any(kw in content for kw in compliance_keywords)

    def _resolve_intent_flags(self, content: str, state: ProjectState) -> tuple[bool, bool]:
        """Combine keyword detection with CLI problem_type_hint."""
        is_sec = self._is_security_intent(content)
        is_ops = self._is_operations_intent(content)
        hint = (state.get("problem_type_hint") or state.get("problem_type") or "").lower()
        if hint in ("security",):
            is_sec = True
        elif hint in ("itil", "operations", "service_management"):
            is_ops = True
        elif hint in ("mixed",):
            is_sec = is_ops = True
        return is_sec, is_ops

    def _build_specialist_queue(self, content: str, state: ProjectState | None = None) -> list[str]:
        """Ordered specialist chain: security before operations when both match."""
        st: ProjectState = state or {}  # type: ignore[assignment]
        is_sec, is_ops = self._resolve_intent_flags(content, st)
        return self._planner.build_specialist_queue(
            content,
            is_security=is_sec,
            is_operations=is_ops,
        )

    def _build_workflow_plan(self, content: str, *, entry_agent: AgentName) -> dict[str, Any]:
        """Return a structured pipeline plan stored on ProjectState."""
        is_sec = self._is_security_intent(content)
        is_ops = self._is_operations_intent(content)
        is_prob = self._is_problem_intent(content)

        if entry_agent == AgentName.PROBLEM_SOLVER:
            plan = self._planner.build_for_problem_loop(content, is_security=is_sec, is_operations=is_ops)
        elif entry_agent == AgentName.SECURITY:
            plan = self._planner.build_for_security_standalone(content)
        elif entry_agent == AgentName.OPERATIONS:
            plan = self._planner.build_for_operations_standalone(content)
        elif entry_agent == AgentName.COMPLIANCE:
            plan = self._planner.build_for_compliance_standalone()
        elif entry_agent == AgentName.DOCUMENT:
            plan = self._planner.build_for_document_standalone()
        else:
            plan = self._planner.build_for_problem_loop(content, is_security=is_sec, is_operations=is_ops)

        return plan.to_dict()

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
            if assigned == AgentName.SECURITY:
                return SupervisorDecision(
                    next_agent=AgentName.SECURITY,
                    reason=f"Open security task: {task.get('title', '')}",
                )
            if assigned == AgentName.OPERATIONS:
                return SupervisorDecision(
                    next_agent=AgentName.OPERATIONS,
                    reason=f"Open operations task: {task.get('title', '')}",
                )

        if messages:
            content = getattr(messages[-1], "content", str(messages[-1])).lower()
            is_sec, is_ops = self._resolve_intent_flags(content, state)
            specialist_queue = self._build_specialist_queue(content, state)

            if self._is_document_intent(content):
                return SupervisorDecision(
                    next_agent=AgentName.DOCUMENT,
                    reason="Document generation intent",
                )

            # Technical problem (+ optional specialist chain) → closed loop at ProblemSolver
            if self._is_problem_intent(content):
                specialists = " → ".join(specialist_queue) if specialist_queue else "none"
                return SupervisorDecision(
                    next_agent=AgentName.PROBLEM_SOLVER,
                    reason=(
                        f"Problem-solving closed loop with specialists: "
                        f"ProblemSolver → [{specialists}] → Compliance"
                    ),
                )

            # Standalone security advisory (等保/测评 without technical problem keywords)
            if is_sec and not self._is_problem_intent(content):
                return SupervisorDecision(
                    next_agent=AgentName.SECURITY,
                    reason="Standalone 等保 security advisory",
                )

            if is_ops and not self._is_problem_intent(content):
                return SupervisorDecision(
                    next_agent=AgentName.OPERATIONS,
                    reason="Standalone ITIL operations advisory",
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

        if should_generate_documents(compliance):
            label = compliance.get("compliance_status", "compliant")
            return SupervisorDecision(
                next_agent=AgentName.DOCUMENT,
                reason=f"Compliance {label} — generating project documents",
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
            next_agent=AgentName.PM_ADVISOR,
            reason=(
                f"non_compliant after {retry_count} retries — "
                "PM advisory before finalize (docs skipped)"
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
        try:
            return self._run_supervisor(state)
        except Exception as exc:
            logger.exception("Supervisor routing failed: %s", exc)
            return {
                "next_agent": AgentName.END.value,
                "agent_errors": list(state.get("agent_errors", []))
                + [
                    {
                        "agent": "supervisor",
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    }
                ],
                "messages": [
                    AIMessage(
                        content=f"[Supervisor] 路由失败，流程终止: {exc}",
                        name="supervisor",
                    )
                ],
            }

    def _run_supervisor(self, state: ProjectState) -> dict[str, Any]:
        """Core supervisor logic (wrapped by __call__ for error recovery)."""
        step = state.get("workflow_step") or WorkflowStep.INITIAL

        if step == WorkflowStep.POST_COMPLIANCE:
            decision = self.decide_after_compliance(state)
        elif step == WorkflowStep.RETRY:
            # Entering retry: increment counter and inject feedback
            compliance = state.get("last_compliance_result") or {}
            retry_count = state.get("compliance_retry_count", 0) + 1
            logger.warning(
                "Compliance retry %d/%d — feedback to ProblemSolver",
                retry_count,
                MAX_COMPLIANCE_RETRIES,
            )
            retry_updates: dict[str, Any] = {
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
            retry_updates.update(
                record_conversation(
                    state,
                    agent="supervisor",
                    event="compliance_retry",
                    summary=f"第 {retry_count} 次合规重试，反馈给 ProblemSolver",
                    detail={
                        "retry_count": retry_count,
                        "compliance_status": compliance.get("compliance_status"),
                        "missing_count": len(compliance.get("missing_items", [])),
                    },
                )
            )
            return retry_updates
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
        if step == WorkflowStep.INITIAL:
            plan = self._build_workflow_plan(last_content, entry_agent=decision.next_agent)
            updates["workflow_plan"] = plan
            stages = plan.get("stages", [])
            log_pipeline_step(
                logger,
                run_id=state.get("run_id", "?"),
                step="pipeline.start",
                detail=f"scenario={plan.get('scenario')} | {' → '.join(stages)}",
            )
            log_pipeline_step(
                logger,
                run_id=state.get("run_id", "?"),
                step="supervisor.plan",
                detail=str(stages),
            )

        if step == WorkflowStep.INITIAL and decision.next_agent == AgentName.PROBLEM_SOLVER:
            updates["active_workflow"] = WORKFLOW_PROBLEM_COMPLIANCE_LOOP
            updates["compliance_retry_count"] = 0
            updates["last_solution"] = None
            updates["last_compliance_result"] = None
            updates["last_security_result"] = None
            updates["last_operations_result"] = None
            updates["last_pm_advice"] = None
            updates["generated_documents"] = []
            updates["agent_errors"] = []
            updates["pipeline_trace"] = []
            updates["specialist_queue"] = self._build_specialist_queue(last_content, {**state, **updates})
            updates["specialists_completed"] = []

        if step == WorkflowStep.INITIAL and decision.next_agent == AgentName.SECURITY:
            if not self._is_problem_intent(last_content):
                updates["active_workflow"] = WORKFLOW_SECURITY_STANDALONE
                updates["specialist_queue"] = [AgentName.SECURITY]
                updates["specialists_completed"] = []
                updates["agent_errors"] = []
                updates["pipeline_trace"] = []

        if step == WorkflowStep.INITIAL and decision.next_agent == AgentName.OPERATIONS:
            if not self._is_problem_intent(last_content):
                updates["active_workflow"] = WORKFLOW_OPERATIONS_STANDALONE
                updates["specialist_queue"] = [AgentName.OPERATIONS]
                updates["specialists_completed"] = []
                updates["agent_errors"] = []
                updates["pipeline_trace"] = []

        if step == WorkflowStep.POST_COMPLIANCE and decision.next_agent == AgentName.PROBLEM_SOLVER:
            log_pipeline_step(
                logger,
                run_id=state.get("run_id", "?"),
                step="supervisor.retry",
                detail=decision.reason,
                level="WARNING",
            )

        log_pipeline_step(
            logger,
            run_id=state.get("run_id", "?"),
            step=f"supervisor.route → {decision.next_agent}",
            detail=decision.reason,
        )
        updates.update(
            record_thinking(
                state,
                agent="supervisor",
                thought=f"分析用户意图，选择入口 Agent: {decision.next_agent}",
                decision=decision.reason,
                evidence=list(updates.get("specialist_queue") or state.get("specialist_queue") or []),
                extra={
                    "next_agent": decision.next_agent.value,
                    "step": str(step),
                    "confidence": decision.confidence,
                },
            )
        )
        updates.update(
            record_conversation(
                state,
                agent="supervisor",
                event="route",
                summary=f"路由到 {decision.next_agent}: {decision.reason}",
                detail={"next_agent": decision.next_agent.value, "step": str(step)},
            )
        )
        return updates


# ---------------------------------------------------------------------------
# LangGraph conditional edge routers (imported by workflow.py)
# ---------------------------------------------------------------------------


def _pending_specialist(state: ProjectState) -> str | None:
    """Return the next specialist in queue not yet completed."""
    queue = state.get("specialist_queue", [])
    done = set(state.get("specialists_completed", []))
    for specialist in queue:
        if specialist not in done:
            return specialist
    return None


def route_after_supervisor(state: ProjectState) -> str:
    """Map supervisor next_agent to graph node."""
    next_agent = state.get("next_agent")
    if next_agent == AgentName.PROBLEM_SOLVER:
        return AgentName.PROBLEM_SOLVER
    if next_agent == AgentName.COMPLIANCE:
        return AgentName.COMPLIANCE
    if next_agent == AgentName.SECURITY:
        return AgentName.SECURITY
    if next_agent == AgentName.OPERATIONS:
        return AgentName.OPERATIONS
    if next_agent == AgentName.DOCUMENT:
        return AgentName.DOCUMENT
    if next_agent == AgentName.PM_ADVISOR:
        return AgentName.PM_ADVISOR
    if next_agent == AgentName.FINALIZE:
        return AgentName.FINALIZE
    return AgentName.END


def route_after_problem_solver(state: ProjectState) -> str:
    """After ProblemSolver: run queued specialists, then Compliance."""
    if state.get("active_workflow") != WORKFLOW_PROBLEM_COMPLIANCE_LOOP:
        return AgentName.END
    pending = _pending_specialist(state)
    if pending == AgentName.SECURITY:
        return AgentName.SECURITY
    if pending == AgentName.OPERATIONS:
        return AgentName.OPERATIONS
    return AgentName.COMPLIANCE


def route_after_specialist_chain(state: ProjectState) -> str:
    """Continue specialist queue or proceed to Compliance in closed loop."""
    if state.get("active_workflow") != WORKFLOW_PROBLEM_COMPLIANCE_LOOP:
        return AgentName.PM_ADVISOR
    pending = _pending_specialist(state)
    if pending == AgentName.SECURITY:
        return AgentName.SECURITY
    if pending == AgentName.OPERATIONS:
        return AgentName.OPERATIONS
    return AgentName.COMPLIANCE


def route_after_security(state: ProjectState) -> str:
    """Standalone security → Compliance; closed loop → next specialist or Compliance."""
    if state.get("active_workflow") == WORKFLOW_SECURITY_STANDALONE:
        return AgentName.COMPLIANCE
    return route_after_specialist_chain(state)


def route_after_operations(state: ProjectState) -> str:
    """Standalone operations → PMAdvisor; closed loop → next specialist or Compliance."""
    if state.get("active_workflow") == WORKFLOW_OPERATIONS_STANDALONE:
        return AgentName.PM_ADVISOR
    return route_after_specialist_chain(state)


def route_after_compliance(state: ProjectState) -> str:
    """
    After Compliance in closed loop → supervisor post-compliance routing.
    Standalone compliance audit → finalize directly.
    """
    if state.get("active_workflow") == WORKFLOW_PROBLEM_COMPLIANCE_LOOP:
        return AgentName.SUPERVISOR

    return AgentName.PM_ADVISOR


def supervisor_post_compliance_node(state: ProjectState) -> dict[str, Any]:
    """
    Wrapper node: set workflow_step=post_compliance then run supervisor logic.

    Separated so the graph can route compliance → supervisor → problem_solver|finalize.
    """
    try:
        state_with_step = {**state, "workflow_step": WorkflowStep.POST_COMPLIANCE}
        supervisor = Supervisor()
        result = supervisor(state_with_step)

        # If supervisor decides to retry, route through retry step on next supervisor call
        if result.get("next_agent") == AgentName.PROBLEM_SOLVER.value:
            retry_state = {**state, **result, "workflow_step": WorkflowStep.RETRY}
            return Supervisor()(retry_state)

        return result
    except Exception as exc:
        logger.exception("supervisor_post_compliance failed: %s", exc)
        return {
            "next_agent": AgentName.PM_ADVISOR.value,
            "agent_errors": list(state.get("agent_errors", []))
            + [
                {
                    "agent": "supervisor",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            ],
            "messages": [
                AIMessage(
                    content=f"[Supervisor] 合规后路由失败，跳转 PM 总结: {exc}",
                    name="supervisor",
                )
            ],
        }


def finalize_node(state: ProjectState) -> dict[str, Any]:
    """Emit final combined output: solution + compliance + generated documents."""
    solution = state.get("last_solution") or {}
    compliance = state.get("last_compliance_result") or {}
    generated = state.get("generated_documents", [])
    pm_advice = state.get("last_pm_advice") or {}
    security = state.get("last_security_result") or {}
    operations = state.get("last_operations_result") or {}
    retry_count = state.get("compliance_retry_count", 0)

    rec_id = solution.get("recommended_solution_id", "N/A")
    analysis = solution.get("problem_analysis", "无方案输出")
    comp_status = compliance.get("compliance_status", compliance.get("overall_status", "unknown"))
    risk = compliance.get("risk_level", "unknown")
    missing = compliance.get("missing_items", [])
    next_action = compliance.get("next_action", "")

    doc_generation = "completed" if generated else "skipped"

    agent_errors = state.get("agent_errors", [])
    pipeline_trace = state.get("pipeline_trace", [])
    workflow_plan = state.get("workflow_plan") or {}
    degraded_agents = state.get("degraded_agents", [])

    final_output = {
        "solution": solution,
        "compliance": compliance,
        "generated_documents": generated,
        "pm_advice": pm_advice,
        "security": security,
        "operations": operations,
        "compliance_retry_count": retry_count,
        "document_generation": doc_generation,
        "compliance_status": comp_status,
        "risk_level": risk,
        "workflow_plan": workflow_plan,
        "pipeline_trace": pipeline_trace,
        "agent_errors": agent_errors,
        "degraded_agents": degraded_agents,
        "run_id": state.get("run_id"),
    }

    lines = [
        "# Forge 完整执行结果",
        "",
        f"**合规重试次数**: {retry_count}",
        f"**最终合规状态**: {comp_status}",
        f"**风险等级**: {risk}",
        f"**资料生成**: {doc_generation} ({len(generated)} 份)",
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
            lines.append(
                f"- **{mod.get('module_name', mod.get('module'))}**: "
                f"{mod.get('status')} (score {mod.get('score')})"
            )
    else:
        lines.append(f"- 状态: {compliance.get('overall_status', 'N/A')}")

    if missing:
        lines.extend(["", "## 合规缺口", *[f"- {m}" for m in missing[:10]]])

    if compliance.get("recommendations"):
        lines.extend(["", "## 整改建议", *[f"- {r}" for r in compliance["recommendations"][:5]]])

    if next_action:
        lines.extend(["", "## 下一步行动", next_action])

    if generated:
        lines.extend(["", "## DocumentAgent 生成资料", ""])
        for doc in generated:
            lines.append(f"### [{doc.get('doc_type')}] {doc.get('title')}")
            lines.append(doc.get("content", "")[:800])
            lines.append("")

    if security.get("diagnosis"):
        lines.extend(
            [
                "",
                "## SecurityAgent 等保安全分析",
                security.get("diagnosis", ""),
                f"- 风险等级: {security.get('risk_level', 'N/A')}",
            ]
        )

    if operations.get("situation_summary"):
        lines.extend(
            [
                "",
                "## OperationsAgent ITIL 运维分析",
                operations.get("situation_summary", ""),
                f"- 实践域: {operations.get('practice_area', 'N/A')}",
            ]
        )

    if pm_advice.get("summary"):
        lines.extend(
            [
                "",
                "## PMAdvisor 项目经理摘要",
                pm_advice.get("summary", ""),
                "",
                "### 行动项",
                *[
                    f"- [{a.get('priority', 'P2')}] {a.get('title', '')}"
                    for a in pm_advice.get("action_items", [])[:8]
                ],
            ]
        )

    log_pipeline_step(
        logger,
        run_id=state.get("run_id", "?"),
        step="finalize",
        detail=(
            f"compliance={comp_status} risk={risk} docs={len(generated)} "
            f"retries={retry_count} errors={len(agent_errors)}"
        ),
    )

    finalize_updates: dict[str, Any] = {
        "next_agent": AgentName.END.value,
        "workflow_step": None,
        "active_workflow": None,
        "final_output": final_output,
        "messages": [AIMessage(content="\n".join(lines), name="forge_finalize")],
    }
    finalize_updates.update(
        record_conversation(
            state,
            agent="supervisor",
            event="finalize",
            summary=f"流程结束 | 合规={comp_status} | 资料={doc_generation}",
            detail=final_output,
        )
    )
    return finalize_updates


def _safe_json(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False, indent=2)[:4000]
