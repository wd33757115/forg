"""Tests for PipelineOrchestrator routing."""

from __future__ import annotations

from forge.core import create_initial_state
from forge.core.orchestrator import PipelineOrchestrator
from forge.core.pipeline import STAGE_COMPLIANCE, STAGE_DOCUMENT, STAGE_PM_ADVISOR, STAGE_PROBLEM_SOLVER


def test_orchestrator_security_problem_queue():
    orch = PipelineOrchestrator()
    state = create_initial_state("orch-sec")
    ctx = orch.resolve_context(state, "等保三级登录401认证失败")
    assert ctx.problem_type == "security"
    assert "security" in ctx.specialist_queue
    plan = orch.build_problem_loop_plan(ctx)
    assert plan.stages[0] == STAGE_PROBLEM_SOLVER
    assert STAGE_COMPLIANCE in plan.stages
    assert STAGE_DOCUMENT in plan.stages
    assert STAGE_PM_ADVISOR in plan.stages


def test_orchestrator_itil_problem_queue():
    orch = PipelineOrchestrator()
    state = create_initial_state("orch-itil")
    ctx = orch.resolve_context(state, "ITIL事件：核心交换机中断导致SLA违约")
    assert ctx.problem_type == "service_management"
    assert "operations" in ctx.specialist_queue


def test_orchestrator_mixed_from_hint():
    orch = PipelineOrchestrator()
    state = create_initial_state("orch-mixed")
    state["problem_type_hint"] = "mixed"
    ctx = orch.resolve_context(state, "系统故障需要综合处理")
    assert "security" in ctx.specialist_queue
    assert "operations" in ctx.specialist_queue


def test_orchestrator_describe_flow():
    orch = PipelineOrchestrator()
    state = create_initial_state("orch-desc")
    ctx = orch.resolve_context(state, "等保测评材料缺口")
    plan = orch.build_problem_loop_plan(ctx)
    desc = orch.describe_flow(plan)
    assert "problem_solver" in desc
    assert "→" in desc
