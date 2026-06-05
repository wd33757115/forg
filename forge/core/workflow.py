"""LangGraph workflow — structured multi-agent pipeline orchestration."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from forge.core.state import ProjectState
from forge.core.supervisor import (
    AgentName,
    Supervisor,
    finalize_node,
    route_after_compliance,
    route_after_operations,
    route_after_problem_solver,
    route_after_security,
    route_after_supervisor,
    supervisor_post_compliance_node,
)
from forge.utils.agent_runner import wrap_agent_node


def build_workflow() -> StateGraph:
    """
    Construct the Forge StateGraph.

    Standard problem-solving pipeline (Supervisor planned):
        ProblemSolver → (Security|Operations)* → Compliance
            → (retry ≤2) → Document → PMAdvisor → Finalize

    All agent nodes are wrapped with ``wrap_agent_node`` for tracing and error recovery.
    """
    from forge.agents.compliance import compliance_node
    from forge.agents.document import document_node
    from forge.agents.operations import operations_node
    from forge.agents.pm_advisor import pm_advisor_node
    from forge.agents.problem_solver import problem_solver_node
    from forge.agents.security import security_node

    supervisor = Supervisor()
    graph = StateGraph(ProjectState)

    graph.add_node(AgentName.SUPERVISOR, supervisor)
    graph.add_node("supervisor_post_compliance", supervisor_post_compliance_node)
    graph.add_node(
        AgentName.PROBLEM_SOLVER,
        wrap_agent_node(problem_solver_node, AgentName.PROBLEM_SOLVER, optional=False),
    )
    graph.add_node(
        AgentName.COMPLIANCE,
        wrap_agent_node(compliance_node, AgentName.COMPLIANCE, optional=False),
    )
    graph.add_node(
        AgentName.SECURITY,
        wrap_agent_node(security_node, AgentName.SECURITY, optional=True),
    )
    graph.add_node(
        AgentName.OPERATIONS,
        wrap_agent_node(operations_node, AgentName.OPERATIONS, optional=True),
    )
    graph.add_node(
        AgentName.DOCUMENT,
        wrap_agent_node(document_node, AgentName.DOCUMENT, optional=True),
    )
    graph.add_node(
        AgentName.PM_ADVISOR,
        wrap_agent_node(pm_advisor_node, AgentName.PM_ADVISOR, optional=True),
    )
    graph.add_node(AgentName.FINALIZE, finalize_node)

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
    graph.add_edge(AgentName.PM_ADVISOR, AgentName.FINALIZE)
    graph.add_edge(AgentName.FINALIZE, END)

    return graph


def compile_workflow():
    """Return a compiled, invokable LangGraph application."""
    return build_workflow().compile()
