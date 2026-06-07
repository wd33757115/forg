"""Pipeline orchestrator — structured multi-agent flow composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forge.agents.problem_classifier import ProblemType, classify_problem
from forge.core.pipeline import (
    STAGE_COMPLIANCE,
    STAGE_DOCUMENT,
    STAGE_OPERATIONS,
    STAGE_PM_ADVISOR,
    STAGE_PROBLEM_SOLVER,
    STAGE_SECURITY,
    PipelinePlan,
    PipelinePlanner,
)
from forge.core.state import (
    WORKFLOW_OPERATIONS_STANDALONE,
    WORKFLOW_PROBLEM_COMPLIANCE_LOOP,
    WORKFLOW_SECURITY_STANDALONE,
    ProjectState,
)

# Standard closed-loop backbone (always in this order after specialists)
CORE_TAIL: list[str] = [
    STAGE_COMPLIANCE,
    STAGE_DOCUMENT,
    STAGE_PM_ADVISOR,
]


@dataclass(frozen=True)
class OrchestrationContext:
    """Resolved routing context for a user request.

    D4: includes classification_confidence and is_uncertain to drive
    adaptive specialist routing and downstream strategy (PS investigation depth).
    """

    content: str
    problem_type: ProblemType
    type_reason: str
    is_security: bool
    is_operations: bool
    is_problem: bool
    specialist_queue: list[str]
    classification_confidence: float = 0.5
    is_uncertain: bool = False


class PipelineOrchestrator:
    """
    Compose Forge execution pipelines in a structured, declarative way.

    Standard problem-solving flow:
        ProblemSolver → (Security|Operations)* → Compliance → Document → PMAdvisor

    Specialist agents are selected from problem type + keyword intent.
    """

    def __init__(self, planner: PipelinePlanner | None = None) -> None:
        self._planner = planner or PipelinePlanner()

    def resolve_context(self, state: ProjectState, content: str) -> OrchestrationContext:
        """Classify problem and decide which specialist agents to invoke.

        D4: captures classification_confidence and widens specialist queue for
        uncertain / mixed cases to ensure broader coverage ("不确定时走 mixed + 更多工具").
        """
        lower = content.lower()
        hint = state.get("problem_type_hint") or state.get("problem_type")
        problem_type, type_reason, conf = classify_problem(content, hint=hint)

        is_security = self._keyword_security(lower)
        is_operations = self._keyword_operations(lower)
        is_problem = self._keyword_problem(lower)

        # Apply CLI / state hints
        if hint:
            h = str(hint).lower()
            if h in ("security",):
                is_security = True
            elif h in ("itil", "operations", "service_management"):
                is_operations = True
            elif h == "mixed":
                is_security = is_operations = True

        # D4: low confidence or explicit mixed → widen routing (include both specialists if relevant)
        is_uncertain = conf < 0.55 or problem_type == "mixed"
        if is_uncertain:
            # For uncertain cases, pull security + operations coverage unless CLI hint strongly narrows
            if not (hint and str(hint).lower() in ("security", "itil", "operations", "service_management")):
                is_security = is_security or True
                is_operations = is_operations or (problem_type in ("mixed", "service_management") or conf < 0.50)

        specialist_queue = self._specialists_for_type(
            problem_type,
            is_security=is_security,
            is_operations=is_operations,
        )

        return OrchestrationContext(
            content=content,
            problem_type=problem_type,
            type_reason=type_reason,
            is_security=is_security,
            is_operations=is_operations,
            is_problem=is_problem,
            specialist_queue=specialist_queue,
            classification_confidence=round(conf, 3),
            is_uncertain=bool(is_uncertain),
        )

    def build_problem_loop_plan(self, ctx: OrchestrationContext) -> PipelinePlan:
        """Full closed loop: PS → specialists → compliance → document → PM."""
        stages = [STAGE_PROBLEM_SOLVER, *ctx.specialist_queue, *CORE_TAIL]
        return PipelinePlan(
            workflow=WORKFLOW_PROBLEM_COMPLIANCE_LOOP,
            stages=stages,
            specialist_queue=list(ctx.specialist_queue),
            scenario=self._planner.detect_scenario(
                ctx.content,
                is_security=ctx.is_security,
                is_operations=ctx.is_operations,
                is_problem=True,
            ),
        )

    def describe_flow(self, plan: PipelinePlan) -> str:
        """Human-readable pipeline description for logs / conversation history."""
        return " → ".join(plan.stages)

    @staticmethod
    def _specialists_for_type(
        problem_type: ProblemType,
        *,
        is_security: bool,
        is_operations: bool,
    ) -> list[str]:
        """Map problem type to ordered specialist agent queue."""
        queue: list[str] = []
        if problem_type in ("security", "mixed"):
            queue.append(STAGE_SECURITY)
        if problem_type in ("service_management", "mixed"):
            queue.append(STAGE_OPERATIONS)
        # Technical-only: use keywords as tie-breaker
        if not queue:
            if is_security:
                queue.append(STAGE_SECURITY)
            if is_operations:
                queue.append(STAGE_OPERATIONS)
        return queue

    @staticmethod
    def _keyword_security(content: str) -> bool:
        keys = ("等保", "安全", "测评", "401", "403", "认证", "防火墙", "审计", "security")
        return any(k in content for k in keys)

    @staticmethod
    def _keyword_operations(content: str) -> bool:
        keys = ("itil", "事件", "sla", "变更", "运维", "中断", "宕机", "incident", "cmdb")
        return any(k in content for k in keys)

    @staticmethod
    def _keyword_problem(content: str) -> bool:
        keys = ("问题", "故障", "problem", "根因", "异常", "报错", "失败", "诊断")
        return any(k in content for k in keys)


def standalone_workflow_for_agent(agent: str) -> str | None:
    """Return workflow id for standalone specialist entry points."""
    if agent == STAGE_SECURITY:
        return WORKFLOW_SECURITY_STANDALONE
    if agent == STAGE_OPERATIONS:
        return WORKFLOW_OPERATIONS_STANDALONE
    return None


def specialists_for_type(
    problem_type: ProblemType, *, is_security: bool, is_operations: bool
) -> list[str]:
    """
    Single source of truth for the ordered specialist agent queue.

    Problem type (security / service_management / mixed) takes precedence;
    keywords act as tie-breaker only for pure 'technical' cases.

    All callers (Orchestrator, Planner, Supervisor) should prefer this function
    for the main problem-solving flow (P1 unification).
    """
    return PipelineOrchestrator._specialists_for_type(
        problem_type, is_security=is_security, is_operations=is_operations
    )


def orchestration_metadata(ctx: OrchestrationContext, plan: PipelinePlan) -> dict[str, Any]:
    """Serializable snapshot for conversation_history / workflow_plan."""
    return {
        "problem_type": ctx.problem_type,
        "type_reason": ctx.type_reason,
        "specialist_queue": ctx.specialist_queue,
        "stages": plan.stages,
        "scenario": plan.scenario,
    }
