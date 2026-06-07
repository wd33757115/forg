"""Helpers to resolve Rule Pack references for agent outputs."""

from __future__ import annotations

from forge.agents.problem_classifier import ProblemType, modules_for_problem_type
from forge.agents.solution_output import RulePackReference
from forge.core.rule_pack import DEFAULT_PACK_FILE, RulePack

# Keyword → preferred rule_ids for stronger offline/LLM reference coverage
_TYPE_KEYWORD_RULES: dict[ProblemType, list[tuple[str, list[str]]]] = {
    "security": [
        ("401", ["db-acs-001"]),
        ("403", ["db-acs-001"]),
        ("登录", ["db-acs-001"]),
        ("认证", ["db-acs-001", "db-aud-001"]),
        ("auth", ["db-acs-001"]),
        ("审计", ["db-aud-001"]),
        ("防火墙", ["db-bnd-001"]),
        ("边界", ["db-bnd-001"]),
        ("等保", ["db-acs-001", "db-aud-001"]),
    ],
    "service_management": [
        ("事件", ["itil-inc-001"]),
        ("itil", ["itil-inc-001", "itil-chg-001"]),
        ("sla", ["itil-slm-001"]),
        ("中断", ["itil-inc-001"]),
        ("变更", ["itil-chg-001"]),
        ("cmdb", ["itil-cfg-001"]),
        ("配置", ["itil-cfg-001"]),
        ("问题", ["itil-prb-001"]),
    ],
    "technical": [
        ("超时", ["si-int-001", "si-test-001"]),
        ("timeout", ["si-int-001"]),
        ("连接池", ["si-int-001"]),
        ("数据库", ["si-int-001"]),
        ("接口", ["si-int-001"]),
        ("性能", ["si-test-001"]),
    ],
    "mixed": [
        ("401", ["db-acs-001"]),
        ("中断", ["itil-inc-001"]),
        ("交换机", ["itil-inc-001", "db-bnd-001"]),
    ],
}


def _append_ref(
    refs: list[RulePackReference],
    seen: set[str],
    *,
    rule_id: str,
    module: str,
    pack: RulePack,
    relevance: str = "",
) -> None:
    if rule_id in seen:
        return
    mod = pack.get_module(module)
    if mod is None:
        return
    rule = mod.get_rule(rule_id)
    if rule is None:
        return
    seen.add(rule_id)
    refs.append(
        RulePackReference(
            rule_id=rule.id,
            module=module,
            title=rule.title,
            relevance=relevance or rule.description[:120],
        )
    )


def fetch_relevant_rules(
    problem_type: ProblemType,
    problem_text: str,
    *,
    limit: int = 6,
    minimum: int = 3,
) -> list[RulePackReference]:
    """Return Rule Pack rules most relevant to the problem type and keywords."""
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    modules = modules_for_problem_type(problem_type)
    lower = problem_text.lower()
    refs: list[RulePackReference] = []
    seen: set[str] = set()

    # 1) Keyword-triggered canonical rule_ids
    for keyword, rule_ids in _TYPE_KEYWORD_RULES.get(problem_type, []):
        if keyword.lower() in lower:
            for rid in rule_ids:
                mod = _module_for_rule_id(rid)
                _append_ref(refs, seen, rule_id=rid, module=mod, pack=pack, relevance=f"关键词「{keyword}」关联")

    # 2) Score rules in priority modules
    for mod_id in modules:
        module = pack.get_module(mod_id)
        if module is None:
            continue
        scored: list[tuple[int, object]] = []
        for rule in module.rules:
            score = 0
            if rule.id.lower() in lower or rule.title in problem_text:
                score += 3
            if rule.category and rule.category in lower:
                score += 2
            for check in rule.checks:
                frag = check.split(":")[-1] if ":" in check else check
                if frag and frag.lower() in lower:
                    score += 1
            if score > 0:
                scored.append((score, rule))
        scored.sort(key=lambda x: -x[0])
        for _, rule in scored[: max(2, limit // len(modules))]:
            _append_ref(
                refs,
                seen,
                rule_id=rule.id,
                module=mod_id,
                pack=pack,
            )
        if len(refs) >= limit:
            break

    # 3) Pad to minimum with type defaults
    defaults: dict[ProblemType, list[tuple[str, str]]] = {
        "security": [("db-acs-001", "dengbao_2.0"), ("db-aud-001", "dengbao_2.0"), ("db-bnd-001", "dengbao_2.0")],
        "service_management": [
            ("itil-inc-001", "itil_iso20000"),
            ("itil-chg-001", "itil_iso20000"),
            ("itil-cfg-001", "itil_iso20000"),
        ],
        "technical": [("si-doc-001", "base_si"), ("si-int-001", "base_si"), ("si-test-001", "base_si")],
        "mixed": [
            ("db-acs-001", "dengbao_2.0"),
            ("itil-inc-001", "itil_iso20000"),
            ("si-doc-001", "base_si"),
        ],
    }
    for rule_id, mod_id in defaults.get(problem_type, defaults["technical"]):
        if len(refs) >= minimum:
            break
        _append_ref(refs, seen, rule_id=rule_id, module=mod_id, pack=pack, relevance="类型默认引用")

    return refs[:limit]


def _module_for_rule_id(rule_id: str) -> str:
    if rule_id.startswith("db-"):
        return "dengbao_2.0"
    if rule_id.startswith("itil-"):
        return "itil_iso20000"
    return "base_si"


def merge_rule_pack_references(
    existing: list[RulePackReference],
    extra_ids: list[str],
    *,
    limit: int = 8,
) -> list[RulePackReference]:
    """Merge extracted rule_ids into reference list (dedupe by rule_id)."""
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    refs = list(existing)
    seen = {r.rule_id for r in refs}
    for rid in extra_ids:
        if rid in seen:
            continue
        mod_id = _module_for_rule_id(rid)
        before = len(refs)
        _append_ref(refs, seen, rule_id=rid, module=mod_id, pack=pack, relevance="调研材料引用")
        if len(refs) == before:
            continue
        if len(refs) >= limit:
            break
    return refs[:limit]


def ensure_minimum_references(
    refs: list[RulePackReference],
    problem_type: ProblemType,
    problem_text: str,
    *,
    minimum: int = 3,
) -> list[RulePackReference]:
    """Guarantee at least ``minimum`` canonical Rule Pack references."""
    if len(refs) >= minimum:
        return refs
    padded = fetch_relevant_rules(problem_type, problem_text, minimum=minimum, limit=max(minimum, 6))
    seen = {r.rule_id for r in refs}
    merged = list(refs)
    for ref in padded:
        if ref.rule_id not in seen:
            merged.append(ref)
            seen.add(ref.rule_id)
        if len(merged) >= minimum:
            break
    return merged
