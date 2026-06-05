"""Tests for OperationsAgent and operations tools."""

from langchain_core.messages import HumanMessage

from forge.agents.operations import OperationsAgent
from forge.agents.operations_output import OperationsOutput
from forge.core import create_initial_state
from forge.core.supervisor import Supervisor
from forge.tools.operations_tools import build_operations_tools, run_operations_research


def test_operations_intent_detection():
    sup = Supervisor()
    assert sup._is_operations_intent("ITIL事件：核心交换机故障")
    assert sup._is_operations_intent("变更管理 CAB 审批")
    assert not sup._is_operations_intent("等保三级测评")


def test_operations_tools_count():
    state = create_initial_state("ops-test")
    tools = build_operations_tools(state)
    assert len(tools) == 6
    assert any(t.name == "query_itil_rules" for t in tools)


def test_operations_offline_research():
    state = create_initial_state("ops-test")
    text = run_operations_research(state, "核心交换机故障导致业务中断")
    assert "itil_iso20000" in text


def test_operations_agent_heuristic():
    state = create_initial_state("ops-test", current_phase="implementation")
    state["messages"] = [HumanMessage(content="ITIL事件：核心交换机故障")]
    state["last_solution"] = {
        "problem_analysis": "交换机故障",
        "root_causes": ["硬件失效"],
        "recommended_solution_id": "sol-a",
        "solutions": [{"id": "sol-a", "title": "更换设备"}],
    }

    result = OperationsAgent().run(state)
    assert result["last_operations_result"]
    ops = result["last_operations_result"]
    assert ops["practice_area"] in ("incident", "mixed")
    assert ops["incident_guidance"] is not None
    assert "operations" in result["specialists_completed"]


def test_operations_output_json():
    out = OperationsOutput(practice_area="incident", situation_summary="测试")
    assert "incident" in out.to_display_json()
