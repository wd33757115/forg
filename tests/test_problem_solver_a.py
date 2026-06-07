"""ProblemSolver depth optimization (A1–A5) tests."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from forge.agents.problem_classifier import classify_with_cli_hint
from forge.agents.problem_solver import ProblemSolverAgent
from forge.agents.rule_pack_refs import fetch_relevant_rules
from forge.agents.solution_output import RulePackReference, SolutionOption, SolutionOutput
from forge.core import create_initial_state
from forge.tools.problem_solver_tools import run_tool_research
from forge.utils.knowledge_memory import search_similar_cases
from forge.utils.metrics import solution_high_relevance_rate
from forge.utils.react_research_gate import supplement_rule_pack_research
from forge.utils.reference_scoring import apply_relevance_scores, score_rule_pack_reference
from scripts.seed_demo_knowledge import seed_state


def test_classify_conflict_dict():
    _ptype, _reason, conflict, _conf = classify_with_cli_hint(
        "数据库连接池耗尽导致接口超时",
        "security",
    )
    assert conflict is not None
    assert conflict["hinted_type"] == "security"
    assert conflict["auto_type"] == "technical"
    assert "warning" in conflict


def test_relevance_score_prefers_research_over_pad():
    research_ref = RulePackReference(
        rule_id="db-acs-001",
        module="dengbao_2.0",
        title="身份鉴别",
        relevance="登录401违反 db-acs-001 身份鉴别，需核查密码策略与失败锁定",
        reference_source="research",
    )
    pad_ref = RulePackReference(
        rule_id="db-bnd-001",
        module="dengbao_2.0",
        title="边界防护",
        relevance="类型默认引用",
        reference_source="minimum_pad",
    )
    text = "登录401身份鉴别"
    assert score_rule_pack_reference(research_ref, text) > score_rule_pack_reference(
        pad_ref, text
    )


def test_apply_relevance_scores_sorts_descending():
    refs = fetch_relevant_rules("security", "登录401认证", minimum=3, limit=5)
    scored = apply_relevance_scores(refs, "登录401认证")
    assert all(r.relevance_score > 0 for r in scored)
    assert scored == sorted(scored, key=lambda r: -r.relevance_score)


def test_research_gate_supplements_thin_context():
    state = create_initial_state("gate-test")
    thin = "### observation\n无 rule pack 调查"
    enriched, ok = supplement_rule_pack_research(
        state, thin, "security", problem_statement="登录401"
    )
    assert ok is True
    assert "rule_pack_" in enriched
    assert "db-acs" in enriched.lower() or "db-" in enriched


def test_research_gate_skips_rich_context():
    state = create_initial_state("gate-rich")
    rich = run_tool_research(state, "登录401", problem_type="security")
    enriched, ok = supplement_rule_pack_research(
        state, rich, "security", problem_statement="登录401"
    )
    assert ok is False
    assert enriched == rich


def test_confidence_uses_tool_evidence():
    agent = ProblemSolverAgent()
    output = SolutionOutput(
        problem_analysis="test",
        root_causes=["a", "b"],
        solutions=[
            SolutionOption(id="sol-a", title="A", description="d", approach="p"),
            SolutionOption(id="sol-b", title="B", description="d", approach="p"),
        ],
        recommended_solution_id="sol-a",
        next_actions=["x", "y", "z"],
        reasoning="依据 db-acs-001 与 db-aud-001",
        decision_rationale="推荐 sol-a，满足 db-acs-001",
        rule_pack_references=[
            RulePackReference(
                rule_id="db-acs-001",
                module="dengbao_2.0",
                title="身份鉴别",
                relevance="401→db-acs-001",
                reference_source="research",
                relevance_score=0.9,
            ),
            RulePackReference(
                rule_id="db-aud-001",
                module="dengbao_2.0",
                title="审计",
                relevance="审计→db-aud-001",
                reference_source="research",
                relevance_score=0.85,
            ),
            RulePackReference(
                rule_id="db-bnd-001",
                module="dengbao_2.0",
                title="边界",
                relevance="边界",
                reference_source="research",
                relevance_score=0.8,
            ),
        ],
    )
    research = "### rule_pack\ndb-acs-001 db-aud-001 db-bnd-001"
    agent._ensure_reasoning_confidence(output, research_context=research)
    assert output.confidence >= 0.75


def test_search_similar_cases_with_demo_seed():
    state = seed_state("ps-a-seed")
    cases = search_similar_cases(
        state,
        problem_type="security",
        problem_text="登录401身份鉴别失败",
        limit=2,
    )
    assert len(cases) >= 1
    assert cases[0].get("match_reason")


def test_agent_run_sets_reference_provenance():
    state = create_initial_state("ps-a-run")
    state["messages"] = [HumanMessage(content="用户登录接口返回401，请诊断")]
    state["problem_type_hint"] = "security"
    agent = ProblemSolverAgent()
    result = agent.run(state)
    stats = result.get("reference_provenance") or {}
    assert stats.get("total", 0) >= 3
    solution = result.get("last_solution") or {}
    assert solution_high_relevance_rate(solution) >= 0.5
