"""Approval flow state machine (v1.1 base)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from forge.core.approval.models import ApprovalRequest
from forge.core.execution.generator import apply_execution_status
from forge.core.state import ProjectState


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_approval_request(
    state: ProjectState,
    *,
    reason: list[str],
    recommendation: str,
    confidence_score: float,
) -> dict[str, Any]:
    run_id = state.get("run_id", "run")
    compliance = state.get("last_compliance_result") or {}
    req = ApprovalRequest(
        id=f"apr-{run_id}-{uuid4().hex[:6]}",
        status="pending",
        recommendation=recommendation,
        confidence_score=confidence_score,
        risk_level=compliance.get("risk_level"),
        reason=reason,
        created_at=_utc_now(),
    )
    return req.to_state_dict()


def resolve_approval_request(
    request: dict[str, Any],
    *,
    approved: bool,
    resolved_by: str = "cli",
) -> dict[str, Any]:
    updated = dict(request)
    updated["status"] = "approved" if approved else "rejected"
    updated["resolved_at"] = _utc_now()
    updated["resolved_by"] = resolved_by
    return updated


def run_approval_gate(
    state: ProjectState,
    *,
    auto_approve: bool = False,
    force_approve: bool | None = None,
) -> dict[str, Any]:
    """
    Create or resolve approval requests based on confidence recommendation.

    ``force_approve`` from CLI --approve / --reject on resumed state.
    """
    recommendation = state.get("confidence_recommendation") or "needs_review"
    confidence_score = float(state.get("confidence_score") or 0)
    explanation = (state.get("last_confidence_result") or {}).get("explanation") or []
    tasks = list(state.get("execution_tasks") or [])
    existing = list(state.get("approval_requests") or [])
    pending = list(state.get("pending_approvals") or [])

    if recommendation == "block":
        tasks = apply_execution_status(tasks, recommendation="block", approved=False)
        return {
            "execution_tasks": tasks,
            "approval_requests": existing,
            "pending_approvals": [],
            "approval_status": "blocked",
        }

    if recommendation == "auto_execute" or auto_approve:
        tasks = apply_execution_status(tasks, recommendation="auto_execute", approved=True)
        req = create_approval_request(
            state,
            reason=explanation or ["自动执行（高置信度或 --auto-approve）"],
            recommendation=recommendation,
            confidence_score=confidence_score,
        )
        req = resolve_approval_request(req, approved=True, resolved_by="auto")
        return {
            "execution_tasks": tasks,
            "approval_requests": existing + [req],
            "pending_approvals": [],
            "approval_status": "auto_approved",
        }

    # needs_review
    if force_approve is not None:
        approved = force_approve
        req = pending[0] if pending else create_approval_request(
            state,
            reason=explanation,
            recommendation=recommendation,
            confidence_score=confidence_score,
        )
        req = resolve_approval_request(req, approved=approved, resolved_by="cli")
        tasks = apply_execution_status(tasks, recommendation=recommendation, approved=approved)
        remaining = [r for r in pending if r.get("id") != req.get("id")]
        return {
            "execution_tasks": tasks,
            "approval_requests": existing + [req],
            "pending_approvals": remaining,
            "approval_status": "approved" if approved else "rejected",
        }

    req = create_approval_request(
        state,
        reason=explanation,
        recommendation=recommendation,
        confidence_score=confidence_score,
    )
    tasks = apply_execution_status(tasks, recommendation=recommendation, approved=False)
    return {
        "execution_tasks": tasks,
        "approval_requests": existing + [req],
        "pending_approvals": [req],
        "approval_status": "pending",
    }
