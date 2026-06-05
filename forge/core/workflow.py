"""LangGraph workflow — ProblemSolver ↔ Compliance closed-loop orchestration."""

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


def build_workflow() -> StateGraph:
    """
    Construct the Forge StateGraph with closed-loop conditional edges.

    Problem-solving flow:
        supervisor → problem_solver → (security|operations)* → compliance
            → supervisor_post_compliance → (retry) | document → pm_advisor → finalize

    Standalone flows:
        supervisor → security → compliance → pm_advisor → finalize
        supervisor → operations → pm_advisor → finalize
        supervisor → compliance → pm_advisor → finalize
        supervisor → document → pm_advisor → finalize
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
    graph.add_node(AgentName.PROBLEM_SOLVER, problem_solver_node)
    graph.add_node(AgentName.COMPLIANCE, compliance_node)
    graph.add_node(AgentName.SECURITY, security_node)
    graph.add_node(AgentName.OPERATIONS, operations_node)
    graph.add_node(AgentName.DOCUMENT, document_node)
    graph.add_node(AgentName.PM_ADVISOR, pm_advisor_node)
    graph.add_node(AgentName.FINALIZE, finalize_node)

    graph.set_entry_point(AgentName.SUPERVISOR)

    # Supervisor → specialist or finalize
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

    # ProblemSolver → specialist chain or Compliance (closed loop)
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

    # Compliance → post-compliance supervisor (loop) or finalize (standalone)
    graph.add_conditional_edges(
        AgentName.COMPLIANCE,
        route_after_compliance,
        {
            AgentName.SUPERVISOR: "supervisor_post_compliance",
            AgentName.PM_ADVISOR: AgentName.PM_ADVISOR,
        },
    )

    # Post-compliance routing → ProblemSolver retry | Document | PMAdvisor
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

    # Security / Operations → next hop in specialist chain or compliance/pm
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

    # Document → PMAdvisor → Finalize (assemble final_output)
    graph.add_edge(AgentName.DOCUMENT, AgentName.PM_ADVISOR)
    graph.add_edge(AgentName.PM_ADVISOR, AgentName.FINALIZE)
    graph.add_edge(AgentName.FINALIZE, END)

    return graph


def compile_workflow():
    """Return a compiled, invokable LangGraph application."""
    return build_workflow().compile()
