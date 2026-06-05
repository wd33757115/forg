"""Helpers to resolve Rule Pack references for agent outputs."""

from __future__ import annotations

from forge.agents.problem_classifier import ProblemType, modules_for_problem_type
from forge.agents.solution_output import RulePackReference
from forge.core.rule_pack import DEFAULT_PACK_FILE, RulePack


def fetch_relevant_rules(
    problem_type: ProblemType,
    problem_text: str,
    *,
    limit: int = 6,
) -> list[RulePackReference]:
    """Return Rule Pack rules most relevant to the problem type and keywords."""
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    modules = modules_for_problem_type(problem_type)
    lower = problem_text.lower()
    refs: list[RulePackReference] = []

    for mod_id in modules:
        module = pack.get_module(mod_id)
        if module is None:
            continue
        for rule in module.rules:
            score = 0
            if any(k in lower for k in (rule.title, rule.category, rule.id)):
                score += 2
            for check in rule.checks:
                if any(k in lower for k in check.split(":")):
                    score += 1
            if score > 0 or len(refs) < limit // len(modules):
                refs.append(
                    RulePackReference(
                        rule_id=rule.id,
                        module=mod_id,
                        title=rule.title,
                        relevance=rule.description[:120],
                    )
                )
            if len(refs) >= limit:
                break
        if len(refs) >= limit:
            break

    # Pad with module defaults if too few
    if len(refs) < 2:
        defaults = {
            "security": [("db-acs-001", "dengbao_2.0"), ("db-aud-001", "dengbao_2.0")],
            "service_management": [("itil-inc-001", "itil_iso20000"), ("itil-chg-001", "itil_iso20000")],
            "technical": [("si-int-001", "base_si"), ("si-test-001", "base_si")],
            "mixed": [("db-acs-001", "dengbao_2.0"), ("itil-inc-001", "itil_iso20000")],
        }
        for rule_id, mod_id in defaults.get(problem_type, defaults["technical"]):
            module = pack.get_module(mod_id)
            if module is None:
                continue
            rule = module.get_rule(rule_id)
            if rule and not any(r.rule_id == rule_id for r in refs):
                refs.append(
                    RulePackReference(
                        rule_id=rule.id,
                        module=mod_id,
                        title=rule.title,
                        relevance=rule.description[:120],
                    )
                )

    return refs[:limit]
