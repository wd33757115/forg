"""Tests for API result serialization."""

from forge.utils.result_serializer import build_api_response


def test_build_api_response():
    result = {
        "run_id": "abc",
        "project_id": "p1",
        "last_solution": {"recommended_solution_id": "sol-a"},
        "last_compliance_result": {"compliance_status": "partial"},
        "pipeline_trace": [{"agent": "problem_solver", "status": "success"}],
        "agent_errors": [],
        "final_output": {},
    }
    payload = build_api_response(result, question="测试", scenario="general")
    assert payload["run_id"] == "abc"
    assert payload["success"] is True
    assert "problem_solver" in payload["agents"]
    assert payload["solution"]["recommended_solution_id"] == "sol-a"
