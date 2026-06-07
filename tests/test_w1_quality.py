"""W1 quality gates: hint mismatch, reasoning rule_ids, reference provenance."""

import re

import pytest

from forge.agents.problem_classifier import classify_with_cli_hint
from forge.agents.problem_solver import ProblemSolverAgent, _RULE_ID_IN_TEXT
from forge.agents.rule_pack_refs import classify_reference_source, fetch_relevant_rules
from forge.agents.solution_output import RulePackReference, SolutionOption, SolutionOutput
from forge.tools.problem_solver_tools import run_tool_research
from forge.core import create_initial_state


def test_classify_hint_mismatch_warning():
    _ptype, _reason, conflict, _conf = classify_with_cli_hint(
        "数据库连接池耗尽导致接口超时",
        "security",
    )
    assert conflict is not None
    assert conflict.get("hinted_type") == "security"
    assert conflict.get("auto_type") == "technical"


def test_classify_hint_match_no_warning():
    _ptype, _reason, conflict, _conf = classify_with_cli_hint(
        "用户登录401等保身份鉴别",
        "security",
    )
    assert conflict is None


def test_validate_reasoning_contains_rule_id():
    agent = ProblemSolverAgent()
    output = SolutionOutput(
        problem_analysis="test",
        root_causes=["a"],
        solutions=[
            SolutionOption(
                id="sol-a",
                title="A",
                description="d",
                approach="p",
            ),
            SolutionOption(
                id="sol-b",
                title="B",
                description="d",
                approach="p",
            ),
        ],
        recommended_solution_id="sol-a",
        next_actions=["act"],
        reasoning="仅描述现象，未引用条款",
        rule_pack_references=[
            RulePackReference(
                rule_id="db-acs-001",
                module="dengbao_2.0",
                title="身份鉴别",
                relevance="test",
            )
        ],
    )
    validated = agent._validate_solution_output(
        output,
        problem_statement="登录401",
        problem_type="security",
        research_context="",
    )
    assert _RULE_ID_IN_TEXT.search(validated.reasoning or "")


def test_reference_source_minimum_pad():
    refs = fetch_relevant_rules("technical", "无关的随机文本xyz", minimum=3, limit=6)
    sources = {classify_reference_source(r) for r in refs}
    assert "minimum_pad" in sources or "scored" in sources


def test_standards_enrich_adds_citations():
    from forge.utils.standards_enrich import enrich_rule_pack_dict, load_catalog

    catalog = load_catalog()
    sample = {
        "modules": {
            "dengbao_2.0": {
                "rules": [
                    {
                        "id": "db-acs-001",
                        "references": ["GB/T 22239-2019 8.1.4.1"],
                    }
                ]
            }
        }
    }
    enriched, stats = enrich_rule_pack_dict(sample, catalog)
    refs = enriched["modules"]["dengbao_2.0"]["rules"][0]["references"]
    assert len(refs) >= 2
    assert stats["citations_added"] >= 1


def test_react_prior_cases_log(caplog):
    state = create_initial_state("w1-prior", current_phase="implementation")
    state["messages"] = []
    agent = ProblemSolverAgent()
    with caplog.at_level("INFO"):
        agent._run_react(state, "登录401", "security", "test")
    assert any("prior_cases" in r.message for r in caplog.records)
