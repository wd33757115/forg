"""Tests for API result serialization."""

from forge.utils.result_serializer import build_api_response


def test_save_run_result(tmp_path):
    from forge.utils.result_serializer import save_run_result

    result = {
        "run_id": "abc123",
        "project_id": "p1",
        "last_solution": {"recommended_solution_id": "sol-a"},
        "agent_errors": [],
    }
    out = save_run_result(result, tmp_path / "run.json", question="test?", elapsed_ms=1500.0)
    assert out.exists()
    data = out.read_text(encoding="utf-8")
    assert "abc123" in data
    assert "elapsed_ms" in data


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
