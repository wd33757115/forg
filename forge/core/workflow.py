"""LangGraph workflow — wires Supervisor and agent nodes into a runnable graph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from forge.agents.compliance import compliance_node
from forge.agents.document import document_node
from forge.agents.problem_solver import problem_solver_node
from forge.core.state import ProjectState
from forge.core.supervisor import AgentName, Supervisor


def _route_after_supervisor(state: ProjectState) -> str:
    """Conditional edge: map next_agent to graph node name."""
    next_agent = state.get("next_agent")
    if next_agent == AgentName.COMPLIANCE:
        return AgentName.COMPLIANCE
    if next_agent == AgentName.DOCUMENT:
        return AgentName.DOCUMENT
    if next_agent == AgentName.PROBLEM_SOLVER:
        return AgentName.PROBLEM_SOLVER
    return AgentName.END


def build_workflow() -> StateGraph:
    """Construct the Forge StateGraph (uncompiled)."""
    supervisor = Supervisor()
    graph = StateGraph(ProjectState)

    graph.add_node(AgentName.SUPERVISOR, supervisor)
    graph.add_node(AgentName.PROBLEM_SOLVER, problem_solver_node)
    graph.add_node(AgentName.COMPLIANCE, compliance_node)
    graph.add_node(AgentName.DOCUMENT, document_node)

    graph.set_entry_point(AgentName.SUPERVISOR)

    graph.add_conditional_edges(
        AgentName.SUPERVISOR,
        _route_after_supervisor,
        {
            AgentName.PROBLEM_SOLVER: AgentName.PROBLEM_SOLVER,
            AgentName.COMPLIANCE: AgentName.COMPLIANCE,
            AgentName.DOCUMENT: AgentName.DOCUMENT,
            AgentName.END: END,
        },
    )

    # Specialist agents return control to supervisor for multi-step loops (Phase 2)
    for agent in (AgentName.PROBLEM_SOLVER, AgentName.COMPLIANCE, AgentName.DOCUMENT):
        graph.add_edge(agent, END)

    return graph


def compile_workflow():
    """Return a compiled, invokable LangGraph application."""
    return build_workflow().compile()
