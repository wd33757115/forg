"""Tests for extracted supervisor routing module."""

from __future__ import annotations

from forge.core.state import WORKFLOW_PROBLEM_COMPLIANCE_LOOP, create_initial_state
from forge.core.supervisor_routing import (
    route_after_compliance,
    route_after_problem_solver,
    route_after_supervisor,
)


def test_route_after_supervisor_problem_solver():
    state = create_initial_state("route-1")
    state["next_agent"] = "problem_solver"
    assert route_after_supervisor(state) == "problem_solver"


def test_route_after_compliance_closed_loop():
    state = create_initial_state("route-2")
    state["active_workflow"] = WORKFLOW_PROBLEM_COMPLIANCE_LOOP
    assert route_after_compliance(state) == "supervisor"


def test_route_after_problem_solver_to_compliance():
    state = create_initial_state("route-3")
    state["active_workflow"] = WORKFLOW_PROBLEM_COMPLIANCE_LOOP
    state["specialist_queue"] = []
    state["specialists_completed"] = []
    assert route_after_problem_solver(state) == "compliance"
