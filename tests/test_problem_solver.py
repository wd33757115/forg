"""Tests for ProblemSolverAgent, tools, and SolutionOutput."""

import json

import pytest
from langchain_core.messages import HumanMessage

from forge.agents.problem_classifier import classify_problem
from forge.agents.problem_solver import ProblemSolverAgent
from forge.agents.solution_output import SolutionOutput
from forge.core import create_initial_state
from forge.core.tool_registry import get_tool_registry
from forge.tools.problem_solver_tools import (
    build_problem_solver_tools,
    run_tool_research,
)


@pytest.fixture
def base_state():
    state = create_initial_state("ps-test-001", current_phase="implementation")
    state["wbs"] = {
        "design": {"name": "方案设计", "status": "in_progress"},
        "implementation": {"name": "实施部署", "status": "pending"},
    }
    state["messages"] = [HumanMessage(content="用户登录接口返回401，请帮忙诊断")]
    return state


def test_build_problem_solver_tools_count(base_state):
    tools = build_problem_solver_tools(base_state)
    names = {t.name for t in tools}
    assert names == {
        "get_current_project_state",
        "query_rule_pack",
        "get_dengbao_requirements",
        "get_itil_guidance",
        "analyze_impact",
        "search_historical_cases",
    }


def test_get_current_project_state_tool(base_state):
    tools = build_problem_solver_tools(base_state)
    tool = next(t for t in tools if t.name == "get_current_project_state")
    result = json.loads(tool.invoke({}))
    assert result["project_id"] == "ps-test-001"
    assert "design" in result["wbs_items"]


def test_query_rule_pack_tool(base_state):
    tools = build_problem_solver_tools(base_state)
    tool = next(t for t in tools if t.name == "query_rule_pack")
    result = json.loads(tool.invoke({"module": "dengbao_2.0", "category": "", "keyword": ""}))
    assert len(result) >= 1
    assert result[0]["module"] == "dengbao_2.0"


def test_get_dengbao_requirements_tool(base_state):
    tools = build_problem_solver_tools(base_state)
    tool = next(t for t in tools if t.name == "get_dengbao_requirements")
    result = json.loads(tool.invoke({"level": "3"}))
    assert result["level"] == "3"
    assert len(result["level_requirements"]) >= 1


def test_get_itil_guidance_tool(base_state):
    tools = build_problem_solver_tools(base_state)
    tool = next(t for t in tools if t.name == "get_itil_guidance")
    result = json.loads(tool.invoke({"practice": "incident"}))
    assert result["practice"] == "Incident Management"


def test_run_tool_research(base_state):
    research = run_tool_research(base_state, "登录401认证失败")
    assert "project_state" in research
    assert "dengbao_l3" in research


@pytest.mark.parametrize(
    "question,hint,expected",
    [
        ("等保三级登录401认证失败", "security", "security"),
        ("ITIL事件核心交换机中断SLA违约", "itil", "service_management"),
        ("数据库连接池耗尽导致超时", "general", "technical"),
    ],
)
def test_classify_problem_types(question, hint, expected):
    ptype, _reason, _conf = classify_problem(question, hint=hint)
    assert ptype == expected


@pytest.mark.parametrize(
    "question,expected",
    [
        ("用户登录接口返回401请诊断", "security"),
        ("ITIL事件核心交换机中断SLA违约", "service_management"),
        ("数据库连接池耗尽导致接口超时", "technical"),
        ("等保401认证失败同时核心交换机故障中断", "mixed"),
    ],
)
def test_classify_problem_auto_without_hint(question, expected):
    """Auto classification without CLI hint (security / itil / general)."""
    ptype, _reason, _conf = classify_problem(question)
    assert ptype == expected


def test_classify_auth_fault_not_mixed_with_generic_fault_keyword():
    """401 + 故障 should stay security, not mixed."""
    ptype, _, _conf = classify_problem("登录401认证故障请诊断")
    assert ptype == "security"


def test_heuristic_solution_has_at_least_three_rule_refs(base_state):
    agent = ProblemSolverAgent()
    research = run_tool_research(base_state, "用户登录接口返回401")
    solution = agent._build_heuristic_solution(
        base_state,
        "用户登录接口返回401",
        research,
        "security",
        "命中等保/安全关键词",
    )
    validated = agent._validate_solution_output(
        solution,
        problem_statement="用户登录接口返回401",
        problem_type="security",
        research_context=research,
    )
    assert len(validated.rule_pack_references) >= 3
    for ref in validated.rule_pack_references:
        assert ref.rule_id.startswith(("db-", "itil-", "si-"))


def test_problem_solver_resolves_tools_via_registry(base_state):
    agent = ProblemSolverAgent()
    registry = get_tool_registry()
    registry_tools = registry.get_tools("problem_solver", base_state)
    agent_tools = agent.get_tools(base_state)
    assert {t.name for t in agent_tools} == {t.name for t in registry_tools}


def test_heuristic_solution_output_auth(base_state):
    agent = ProblemSolverAgent()
    research = run_tool_research(base_state, "用户登录接口返回401")
    solution = agent._build_heuristic_solution(
        base_state,
        "用户登录接口返回401",
        research,
        "security",
        "命中等保/安全关键词",
    )

    assert isinstance(solution, SolutionOutput)
    assert solution.problem_type == "security"
    assert len(solution.rule_pack_references) >= 3
    assert len(solution.solutions) >= 2
    assert solution.recommended_solution_id in {s.id for s in solution.solutions}
    assert len(solution.root_causes) >= 1
    assert len(solution.next_actions) >= 1
    assert len(solution.dengbao_considerations) >= 1
    assert len(solution.itil_considerations) >= 1


def test_agent_run_produces_structured_knowledge(base_state):
    agent = ProblemSolverAgent()
    result = agent.run(base_state)

    assert result.get("messages")
    kb = result["knowledge_base"]
    assert len(kb) == 1
    assert kb[0]["category"] == "problem_solution"
    assert "solution" in kb[0]["metadata"]
    assert kb[0]["metadata"]["recommended_solution_id"]
    assert result.get("problem_type")
    assert result.get("agent_context", {}).get("compliance")
    solution = result.get("last_solution") or {}
    assert len(solution.get("rule_pack_references") or []) >= 3
    assert "现象：" in solution.get("problem_analysis", "")


def test_solution_output_json_schema():
    sol = SolutionOutput(
        problem_analysis="test",
        root_causes=["a"],
        solutions=[],
        recommended_solution_id="sol-a",
        next_actions=["act"],
    )
    # validation pads solutions in agent; raw model allows empty for this test
    data = sol.model_dump()
    assert "problem_analysis" in data
    assert "recommended_solution_id" in data


def test_d3_execution_feedback_formatting_and_learning():
    """D3: execution feedback is formatted and forces learning citation in reasoning."""
    from forge.agents.problem_solver import _format_execution_feedback, ProblemSolverAgent
    from forge.agents.solution_output import SolutionOutput

    execs = [
        {"task_id": "t1", "status": "failed", "summary": "部署失败：权限不足"},
        {"task_id": "t2", "status": "success", "summary": "回滚成功"},
    ]
    block = _format_execution_feedback(execs)
    assert "过往执行反馈" in block
    assert "t1" in block and "failed" in block

    sol = SolutionOutput(
        problem_analysis="现象",
        root_causes=["c"],
        solutions=[{"id": "s1", "title": "s", "description": "d", "approach": "a", "trade_offs": ["t"], "compliance_impact": "c", "itil_guidance": "i", "estimated_effort": "e", "risk_level": "low"}],
        recommended_solution_id="s1",
        next_actions=["n1"],
        reasoning="基础推理。",
    )
    ProblemSolverAgent._ensure_execution_learning(sol, block)
    assert "过往执行" in sol.reasoning or "参考过往执行" in sol.reasoning


def test_d3_confidence_includes_history_and_exec():
    """D3: _compute_confidence factors positive history and exec results."""
    from forge.agents.problem_solver import ProblemSolverAgent
    from forge.agents.solution_output import SolutionOutput, RulePackReference

    sol = SolutionOutput(
        problem_analysis="p",
        root_causes=["r"],
        solutions=[{"id": "s1", "title": "s", "description": "d", "approach": "a", "trade_offs": ["t"], "compliance_impact": "c", "itil_guidance": "i", "estimated_effort": "e", "risk_level": "low"}],
        recommended_solution_id="s1",
        next_actions=["n"],
        rule_pack_references=[RulePackReference(rule_id="db-acs-001", module="dengbao_2.0", title="t", relevance="现象→规则")],
        reasoning="有 rule_id 的推理。",
    )
    prior = [{"id": "case-1", "outcome": "success"}]
    execs = [{"status": "success"}]
    base = ProblemSolverAgent._compute_confidence(sol, research_context="db-acs-001")
    with_hist = ProblemSolverAgent._compute_confidence(sol, research_context="db-acs-001", prior_cases=prior)
    with_exec = ProblemSolverAgent._compute_confidence(sol, research_context="db-acs-001", execution_results=execs)
    assert with_hist >= base - 0.001  # positive history should not decrease
    assert with_exec >= base - 0.001


# --- Strict prompt/code requirements tests (等保 / ITIL / mixed + quality) ---

@pytest.mark.parametrize(
    "question,ptype_hint,expected_rule_prefixes",
    [
        ("等保三级登录401认证失败，需要诊断与整改", "security", ("db-",)),
        ("ITIL事件：核心交换机中断导致SLA违约，请处理", "itil", ("itil-",)),
        ("等保身份鉴别整改同时发生P1事件中断", None, ("db-", "itil-")),  # mixed should pull from both
    ],
)
def test_ps_strict_requirements_scenarios(base_state, question, ptype_hint, expected_rule_prefixes):
    """Covers 等保, ITIL, mixed. Verifies rule_pack_references validity + reasoning depth + related_knowledge + risks."""
    from forge.agents.problem_solver import ProblemSolverAgent
    from forge.utils.knowledge_memory import search_similar_cases

    if ptype_hint:
        base_state["problem_type_hint"] = ptype_hint

    # Seed a bit of knowledge_base so related_knowledge can be populated (tests the injection path)
    base_state["knowledge_base"] = [
        {"id": "kb-sec-1", "content": "等保登录401历史用重置+审计加固解决", "tags": ["security"], "outcome": "success", "related_rules": ["db-acs-001"]},
        {"id": "kb-itil-1", "content": "P1交换机中断事件走incident+变更流程恢复", "tags": ["service_management"], "outcome": "resolved", "related_rules": ["itil-inc-001"]},
    ]

    agent = ProblemSolverAgent()
    # Use heuristic path (reliable for tests)
    research = run_tool_research(base_state, question)
    # Also exercise the knowledge_helpers path indirectly via search_similar (the code now calls search_knowledge directly too)
    prior = search_similar_cases(base_state, problem_type="security" if "401" in question or "等保" in question else "service_management", problem_text=question, limit=2)

    sol = agent._build_heuristic_solution(
        base_state, question, research, "security" if "401" in question or "等保" in question else ("service_management" if "ITIL" in question or "事件" in question else "mixed"), "test"
    )
    validated = agent._validate_solution_output(
        sol,
        problem_statement=question,
        problem_type=("security" if "401" in question or "等保" in question else ("service_management" if "ITIL" in question or "事件" in question else "mixed")),
        research_context=research,
        state=base_state,
    )

    # rule_pack_references must have >=2 and valid relevant prefixes
    assert len(validated.rule_pack_references) >= 2, "rule_pack_references 必须至少2条"
    prefixes = tuple(p for p in expected_rule_prefixes)
    has_valid = any(any(r.rule_id.startswith(pref) for pref in prefixes) for r in validated.rule_pack_references)
    assert has_valid, f"rule_pack_references 应包含有效相关规则前缀 {prefixes}"

    # reasoning must be structured and cover the required analysis points
    r = (validated.reasoning or "").lower()
    assert len(r) > 80, "reasoning 必须有足够深度"
    # The 5 points in Chinese or English markers from our prompt
    assert any(k in r for k in ["问题分析", "规则依据", "历史参考", "风险考量", "最终方案", "1)", "2)", "3)"]), "reasoning 必须结构化体现5点分析"

    # related_knowledge or explicit "未检索到" statement
    has_related = bool(getattr(validated, "related_knowledge", None)) or "未检索到相关历史案例" in (validated.reasoning or "") or "知识库" in (validated.reasoning or "")
    assert has_related, "必须有 related_knowledge 或明确说明未检索到"

    # confidence present with some basis (we set it)
    assert 0.0 <= validated.confidence <= 1.0

    # risks >=2
    assert len(validated.risks or []) >= 2, "risks 必须至少2个"

    # No total emptiness
    assert validated.decision_rationale
    assert validated.next_actions and len(validated.next_actions) >= 1
