"""LangGraph workflow — structured multi-agent pipeline orchestration."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from forge.core.agent_registry import get_agent_registry
from forge.core.state import ProjectState
from forge.core.supervisor import (
    AgentName,
    Supervisor,
    route_after_compliance,
    route_after_operations,
    route_after_problem_solver,
    route_after_security,
    route_after_supervisor,
    supervisor_post_compliance_node,
)


def build_workflow() -> StateGraph:
    """
    Construct the Forge StateGraph via AgentRegistry.

    Standard pipeline:
        ProblemSolver → (Security|Operations)* → Compliance
            → (retry ≤2) → Document → PMAdvisor
            → Execution → ApprovalGate → Finalize
    """
    registry = get_agent_registry()
    supervisor = Supervisor()
    graph = StateGraph(ProjectState)

    graph.add_node(AgentName.SUPERVISOR, supervisor)
    graph.add_node("supervisor_post_compliance", supervisor_post_compliance_node)

    for name in (
        AgentName.PROBLEM_SOLVER,
        AgentName.COMPLIANCE,
        AgentName.SECURITY,
        AgentName.OPERATIONS,
        AgentName.DOCUMENT,
        AgentName.PM_ADVISOR,
        AgentName.EXECUTION,
        AgentName.APPROVAL_GATE,
        AgentName.FINALIZE,
    ):
        graph.add_node(name, registry.get_node(name.value))

    graph.set_entry_point(AgentName.SUPERVISOR)

    graph.add_conditional_edges(
        AgentName.SUPERVISOR,
        route_after_supervisor,
        {
            AgentName.PROBLEM_SOLVER: AgentName.PROBLEM_SOLVER,
            AgentName.COMPLIANCE: AgentName.COMPLIANCE,
            AgentName.SECURITY: AgentName.SECURITY,
            AgentName.OPERATIONS: AgentName.OPERATIONS,
            AgentName.DOCUMENT: AgentName.DOCUMENT,
            AgentName.PM_ADVISOR: AgentName.PM_ADVISOR,
            AgentName.FINALIZE: AgentName.FINALIZE,
            AgentName.END: END,
        },
    )

    graph.add_conditional_edges(
        AgentName.PROBLEM_SOLVER,
        route_after_problem_solver,
        {
            AgentName.COMPLIANCE: AgentName.COMPLIANCE,
            AgentName.SECURITY: AgentName.SECURITY,
            AgentName.OPERATIONS: AgentName.OPERATIONS,
            AgentName.END: END,
        },
    )

    graph.add_conditional_edges(
        AgentName.COMPLIANCE,
        route_after_compliance,
        {
            AgentName.SUPERVISOR: "supervisor_post_compliance",
            AgentName.PM_ADVISOR: AgentName.PM_ADVISOR,
        },
    )

    graph.add_conditional_edges(
        "supervisor_post_compliance",
        route_after_supervisor,
        {
            AgentName.PROBLEM_SOLVER: AgentName.PROBLEM_SOLVER,
            AgentName.DOCUMENT: AgentName.DOCUMENT,
            AgentName.PM_ADVISOR: AgentName.PM_ADVISOR,
            AgentName.FINALIZE: AgentName.FINALIZE,
            AgentName.END: END,
        },
    )

    graph.add_conditional_edges(
        AgentName.SECURITY,
        route_after_security,
        {
            AgentName.COMPLIANCE: AgentName.COMPLIANCE,
            AgentName.SECURITY: AgentName.SECURITY,
            AgentName.OPERATIONS: AgentName.OPERATIONS,
            AgentName.PM_ADVISOR: AgentName.PM_ADVISOR,
        },
    )
    graph.add_conditional_edges(
        AgentName.OPERATIONS,
        route_after_operations,
        {
            AgentName.COMPLIANCE: AgentName.COMPLIANCE,
            AgentName.SECURITY: AgentName.SECURITY,
            AgentName.OPERATIONS: AgentName.OPERATIONS,
            AgentName.PM_ADVISOR: AgentName.PM_ADVISOR,
        },
    )

    graph.add_edge(AgentName.DOCUMENT, AgentName.PM_ADVISOR)
    graph.add_edge(AgentName.PM_ADVISOR, AgentName.EXECUTION)
    graph.add_edge(AgentName.EXECUTION, AgentName.APPROVAL_GATE)
    graph.add_edge(AgentName.APPROVAL_GATE, AgentName.FINALIZE)
    graph.add_edge(AgentName.FINALIZE, END)

    return graph


def compile_workflow():
    """Return a compiled, invokable LangGraph application."""
    return build_workflow().compile()
