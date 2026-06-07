"""Compliance closed-loop controller (P1 extraction).

Encapsulates:
- Compliance status predicates (is_compliant, should_generate_documents, etc.)
- Retry decision after ComplianceAgent
- MAX_COMPLIANCE_RETRIES constant

This reduces Supervisor bloat and makes the loop testable in isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from forge.core.state import ProjectState
from forge.utils.compliance_feedback import build_compliance_feedback

if TYPE_CHECKING:
    from forge.core.supervisor import SupervisorDecision

# Re-exported for compatibility; single source now lives here.
MAX_COMPLIANCE_RETRIES = 2


def is_compliant(compliance_result: dict[str, Any] | None) -> bool:
    """Return True when overall compliance is considered passing."""
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


class ComplianceLoopController:
    """
    Drives the ProblemSolver <-> Compliance retry loop.

    Used by Supervisor after Compliance runs (via supervisor_post_compliance_node).
    """

    def __init__(self, max_retries: int = MAX_COMPLIANCE_RETRIES) -> None:
        self.max_retries = max_retries

    def decide_after_compliance(self, state: ProjectState) -> "SupervisorDecision":
        """
        After ComplianceAgent runs in the closed loop, decide retry or finalize.

        Returns a SupervisorDecision (next_agent = DOCUMENT | PROBLEM_SOLVER | PM_ADVISOR).
        """
        # Local import to avoid circular dependency at module load time
        from forge.core.supervisor import AgentName, SupervisorDecision

        compliance = state.get("last_compliance_result") or {}
        retry_count = state.get("compliance_retry_count", 0)

        if should_generate_documents(compliance):
            label = compliance.get("compliance_status", "compliant")
            return SupervisorDecision(
                next_agent=AgentName.DOCUMENT,
                reason=f"Compliance {label} — generating project documents",
                confidence=1.0,
            )

        if retry_count < self.max_retries:
            return SupervisorDecision(
                next_agent=AgentName.PROBLEM_SOLVER,
                reason=(
                    f"non_compliant — re-optimizing solution "
                    f"(retry {retry_count + 1}/{self.max_retries})"
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

    def build_retry_updates(
        self,
        state: ProjectState,
        *,
        compliance: dict[str, Any],
        retry_count: int,
    ) -> dict[str, Any]:
        """
        Prepare the state updates when entering a compliance retry.

        Includes:
        - incremented counter
        - structured compliance_feedback (for ProblemSolver)
        - the HumanMessage feedback (with failed_items)
        - conversation history event
        """
        from langchain_core.messages import AIMessage, HumanMessage

        from forge.core.state import WORKFLOW_PROBLEM_COMPLIANCE_LOOP
        from forge.core.supervisor import AgentName
        from forge.utils.conversation import record_conversation

        structured_feedback = build_compliance_feedback(compliance, retry_count=retry_count)

        feedback_msg = self._build_retry_feedback_message(
            compliance, structured_feedback=structured_feedback
        )

        retry_updates: dict[str, Any] = {
            "next_agent": AgentName.PROBLEM_SOLVER.value,
            "compliance_retry_count": retry_count,
            "compliance_feedback": structured_feedback,
            "workflow_step": "initial",  # normalized by caller
            "active_workflow": WORKFLOW_PROBLEM_COMPLIANCE_LOOP,
            "rule_pack": state.get("rule_pack"),  # caller refreshes if needed
            "messages": [
                AIMessage(
                    content=(
                        f"[Supervisor] Compliance retry {retry_count}/{self.max_retries} "
                        "— sending feedback to ProblemSolver"
                    ),
                    name="supervisor",
                ),
                feedback_msg,
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
                    "failed_rule_ids": structured_feedback.get("failed_rule_ids", []),
                },
            )
        )

        return retry_updates

    def _build_retry_feedback_message(
        self,
        compliance: dict[str, Any],
        *,
        structured_feedback: dict[str, Any] | None = None,
    ) -> "HumanMessage":
        """Human readable retry instruction (extracted for controller ownership)."""
        from langchain_core.messages import HumanMessage

        feedback = structured_feedback or build_compliance_feedback(compliance)
        failed = feedback.get("failed_items") or []
        missing = feedback.get("missing_items") or compliance.get("missing_items", [])
        recs = feedback.get("suggestions") or compliance.get("recommendations", [])
        failed_lines = "\n".join(
            f"- [{f.get('status', 'fail')}] `{f.get('rule_id')}` ({f.get('severity', '—')}) "
            f"{f.get('title', '')}: {(f.get('suggestion') or '')[:120]}"
            for f in failed[:8]
        )
        body = (
            "【合规反馈 — 请优化方案】\n"
            f"合规状态: {feedback.get('compliance_status', 'non_compliant')}\n"
            f"检查模式: {feedback.get('check_mode', '—')}\n"
            f"风险等级: {feedback.get('risk_level', 'unknown')}\n\n"
            "失败项 (failed_items — 必须在 reasoning 中逐条响应):\n"
            + (failed_lines if failed_lines else "- 见 state.compliance_feedback")
            + "\n\n缺口:\n"
            + ("\n".join(f"- {m}" for m in missing[:8]) if missing else "- 见上次合规报告")
            + "\n\n整改建议:\n"
            + ("\n".join(f"- {r}" for r in recs[:5]) if recs else "- 请对照 Rule Pack 补齐证据")
            + "\n\n请基于以上合规反馈重新生成更合规的解决方案。"
        )
        return HumanMessage(content=body)
