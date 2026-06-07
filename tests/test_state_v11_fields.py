"""Tests for v1.1 ProjectState fields."""

from __future__ import annotations

from forge.core.state import create_initial_state


def test_initial_state_has_confidence_and_risk():
    state = create_initial_state("v11-fields")
    assert "confidence_score" in state
    assert "risk_level" in state
    assert state["confidence_score"] is None
    assert state["risk_level"] is None
