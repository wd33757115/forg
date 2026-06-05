"""Tests for FastAPI Web API."""

from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web.app import app  # noqa: E402


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_home():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Forge" in r.text


@patch("web.app.run_forge")
def test_solve(mock_run):
    mock_run.return_value = {
        "run_id": "test1234",
        "project_id": "web-demo",
        "last_solution": {"recommended_solution_id": "sol-a", "problem_analysis": "ok"},
        "last_compliance_result": {"compliance_status": "partial", "risk_level": "medium"},
        "pipeline_trace": [{"agent": "problem_solver", "status": "success"}],
        "agent_errors": [],
        "final_output": {},
    }
    client = TestClient(app)
    r = client.post(
        "/solve",
        json={"question": "等保三级登录401故障", "project_id": "web-demo"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == "test1234"
    assert data["solution"]["recommended_solution_id"] == "sol-a"
    assert "problem_solver" in data["agents"]


def test_solve_empty_question():
    client = TestClient(app)
    r = client.post("/solve", json={"question": ""})
    assert r.status_code == 422
