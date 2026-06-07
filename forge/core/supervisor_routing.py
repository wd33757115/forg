"""LangGraph conditional edge routers — extracted from Supervisor (phase 2.4)."""

from __future__ import annotations

from forge.core.state import (
    WORKFLOW_OPERATIONS_STANDALONE,
    WORKFLOW_PROBLEM_COMPLIANCE_LOOP,
    WORKFLOW_SECURITY_STANDALONE,
    ProjectState,
)

# Node name constants (match AgentName StrEnum values in supervisor.py)
PS = "problem_solver"
COMPLIANCE = "compliance"
SECURITY = "security"
OPERATIONS = "operations"
DOCUMENT = "document"
PM = "pm_advisor"
FINALIZE = "finalize"
SUPERVISOR = "supervisor"
END = "__end__"


def _pending_specialist(state: ProjectState) -> str | None:
    queue = state.get("specialist_queue", [])
    done = set(state.get("specialists_completed", []))
    for specialist in queue:
        if specialist not in done:
            return specialist
    return None


def route_after_supervisor(state: ProjectState) -> str:
    next_agent = state.get("next_agent")
    routes = {
        PS: PS,
        COMPLIANCE: COMPLIANCE,
        SECURITY: SECURITY,
        OPERATIONS: OPERATIONS,
        DOCUMENT: DOCUMENT,
        PM: PM,
        FINALIZE: FINALIZE,
    }
    return routes.get(next_agent, END)


def route_after_problem_solver(state: ProjectState) -> str:
    if state.get("active_workflow") != WORKFLOW_PROBLEM_COMPLIANCE_LOOP:
        return END
    pending = _pending_specialist(state)
    if pending == SECURITY:
        return SECURITY
    if pending == OPERATIONS:
        return OPERATIONS
    return COMPLIANCE


def route_after_specialist_chain(state: ProjectState) -> str:
    if state.get("active_workflow") != WORKFLOW_PROBLEM_COMPLIANCE_LOOP:
        return PM
    pending = _pending_specialist(state)
    if pending == SECURITY:
        return SECURITY
    if pending == OPERATIONS:
        return OPERATIONS
    return COMPLIANCE


def route_after_security(state: ProjectState) -> str:
    if state.get("active_workflow") == WORKFLOW_SECURITY_STANDALONE:
        return COMPLIANCE
    return route_after_specialist_chain(state)


def route_after_operations(state: ProjectState) -> str:
    if state.get("active_workflow") == WORKFLOW_OPERATIONS_STANDALONE:
        return PM
    return route_after_specialist_chain(state)


def route_after_compliance(state: ProjectState) -> str:
    if state.get("active_workflow") == WORKFLOW_PROBLEM_COMPLIANCE_LOOP:
        return SUPERVISOR
    return PM
