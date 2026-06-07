"""ReAct research quality gate — ensure Rule Pack tool evidence (ProblemSolver A2)."""

from __future__ import annotations

from typing import Any

from forge.agents.problem_classifier import ProblemType, modules_for_problem_type
from forge.core.state import ProjectState
from forge.tools.problem_solver_tools import _tool_query_rule_pack
from forge.utils.rule_pack_extract import extract_rule_ids_from_text

_MIN_RULE_IDS = 3


def research_has_rule_pack_evidence(research: str) -> bool:
    """True when research text looks like it included Rule Pack query results."""
    lower = (research or "").lower()
    return (
        "query_rule_pack" in lower
        or "rule_pack_" in lower
        or "## rule pack" in lower
        or '"id": "db-' in lower
        or '"id": "itil-' in lower
    )


def supplement_rule_pack_research(
    state: ProjectState | dict[str, Any],
    research: str,
    problem_type: ProblemType,
    *,
    problem_statement: str = "",
) -> tuple[str, bool]:
    """
    Append programmatic ``query_rule_pack`` output when ReAct research is thin.

    Returns (possibly extended research, was_supplemented).
    """
    ids = extract_rule_ids_from_text(research)
    if research_has_rule_pack_evidence(research) and len(ids) >= _MIN_RULE_IDS:
        return research, False

    modules = modules_for_problem_type(problem_type)
    blocks = [
        "\n\n### [gate] query_rule_pack supplement",
        f"problem_type={problem_type} | extracted_rule_ids={len(ids)}",
    ]
    for mod in modules:
        blocks.append(f"### rule_pack_{mod}\n{_tool_query_rule_pack(state, mod, '', '')}")

    if problem_statement and len(ids) < _MIN_RULE_IDS:
        kw = problem_statement[:40].replace("\n", " ")
        blocks.append(
            f"### rule_pack_keyword\n{_tool_query_rule_pack(state, '', '', kw)}"
        )

    return research.rstrip() + "\n\n" + "\n\n".join(blocks), True
