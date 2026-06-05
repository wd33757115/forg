"""LangGraph workflow — ProblemSolver ↔ Compliance closed-loop orchestration."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from forge.core.state import ProjectState
from forge.core.supervisor import (
    AgentName,
    Supervisor,
    finalize_node,
    route_after_compliance,
    route_after_problem_solver,
    route_after_supervisor,
    supervisor_post_compliance_node,
)


def build_workflow() -> StateGraph:
    """
    Construct the Forge StateGraph with closed-loop conditional edges.

    Problem-solving flow:
        supervisor → problem_solver → compliance → supervisor_post_compliance
            → (retry) problem_solver | document → pm_advisor → finalize → END

    Standalone flows:
        supervisor → compliance → pm_advisor → finalize → END
        supervisor → document → pm_advisor → finalize → END
    """
    from forge.agents.compliance import compliance_node
    from forge.agents.document import document_node
    from forge.agents.pm_advisor import pm_advisor_node
    from forge.agents.problem_solver import problem_solver_node

    supervisor = Supervisor()
    graph = StateGraph(ProjectState)

    graph.add_node(AgentName.SUPERVISOR, supervisor)
    graph.add_node("supervisor_post_compliance", supervisor_post_compliance_node)
    graph.add_node(AgentName.PROBLEM_SOLVER, problem_solver_node)
    graph.add_node(AgentName.COMPLIANCE, compliance_node)
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
            AgentName.DOCUMENT: AgentName.DOCUMENT,
            AgentName.PM_ADVISOR: AgentName.PM_ADVISOR,
            AgentName.FINALIZE: AgentName.FINALIZE,
            AgentName.END: END,
        },
    )

    # ProblemSolver → Compliance (closed loop) or END (legacy task)
    graph.add_conditional_edges(
        AgentName.PROBLEM_SOLVER,
        route_after_problem_solver,
        {
            AgentName.COMPLIANCE: AgentName.COMPLIANCE,
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

    # Document → PMAdvisor → Finalize (assemble final_output)
    graph.add_edge(AgentName.DOCUMENT, AgentName.PM_ADVISOR)
    graph.add_edge(AgentName.PM_ADVISOR, AgentName.FINALIZE)
    graph.add_edge(AgentName.FINALIZE, END)

    return graph


def compile_workflow():
    """Return a compiled, invokable LangGraph application."""
    return build_workflow().compile()
