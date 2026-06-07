"""Helpers to resolve Rule Pack references for agent outputs."""

from __future__ import annotations

from forge.agents.problem_classifier import ProblemType, modules_for_problem_type
from forge.agents.solution_output import RulePackReference
from forge.core.rule_pack import DEFAULT_PACK_FILE, RulePack

# D2: simple severity loader (cached lightly via module level for perf in loops)
_SEVERITY_INDEX: dict[str, str] | None = None


def _get_severity_index() -> dict[str, str]:
    global _SEVERITY_INDEX
    if _SEVERITY_INDEX is None:
        pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
        idx: dict[str, str] = {}
        for mod in pack.modules.values():
            for rule in mod.rules:
                idx[rule.id] = rule.severity or "medium"
        _SEVERITY_INDEX = idx
    return _SEVERITY_INDEX

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


def classify_reference_source(ref: RulePackReference) -> str:
    """Infer reference provenance for W1-4 metrics."""
    if ref.reference_source:
        return ref.reference_source
    rel = ref.relevance or ""
    if "关键词" in rel:
        return "keyword"
    if "类型默认" in rel or "默认引用" in rel:
        return "minimum_pad"
    if "调研" in rel:
        return "research"
    return "scored"


def _append_ref(
    refs: list[RulePackReference],
    seen: set[str],
    *,
    rule_id: str,
    module: str,
    pack: RulePack,
    relevance: str = "",
    reference_source: str = "",
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
            reference_source=reference_source,
        )
    )


def fetch_relevant_rules(
    problem_type: ProblemType,
    problem_text: str,
    *,
    limit: int = 6,
    minimum: int = 3,
    check_mode: str | None = None,
) -> list[RulePackReference]:
    """Return Rule Pack rules most relevant to the problem type and keywords.

    D2 extension: when check_mode="strict", bias selection toward higher-severity
    rules (high/critical) so that strict compliance checks get stronger clauses.
    """
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    modules = modules_for_problem_type(problem_type)
    lower = problem_text.lower()
    refs: list[RulePackReference] = []
    seen: set[str] = set()
    strict = (check_mode or "").lower() == "strict"
    sev_index = _get_severity_index() if strict else {}

    def _sev_bonus(rid: str) -> int:
        if not strict:
            return 0
        s = sev_index.get(rid, "medium")
        if s in ("critical", "high"):
            return 4
        if s == "medium":
            return 1
        return 0

    # 1) Keyword-triggered canonical rule_ids (D2: give extra weight in strict)
    for keyword, rule_ids in _TYPE_KEYWORD_RULES.get(problem_type, []):
        if keyword.lower() in lower:
            for rid in rule_ids:
                mod = _module_for_rule_id(rid)
                _append_ref(
                    refs,
                    seen,
                    rule_id=rid,
                    module=mod,
                    pack=pack,
                    relevance=f"关键词「{keyword}」关联",
                    reference_source="keyword",
                )

    # 2) Score rules in priority modules (D2: severity boost for strict)
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
            score += _sev_bonus(rule.id)  # D2 strict bias
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
                reference_source="scored",
            )
        if len(refs) >= limit:
            break

    # 3) Pad to minimum with type defaults (D2: for strict, prefer high-sev first)
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
    default_list = defaults.get(problem_type, defaults["technical"])
    if strict:
        # sort defaults so high-severity come first
        default_list = sorted(
            default_list,
            key=lambda t: (0 if _get_severity_index().get(t[0], "medium") in ("high", "critical") else 1, t[0])
        )
    for rule_id, mod_id in default_list:
        if len(refs) >= minimum:
            break
        _append_ref(
            refs,
            seen,
            rule_id=rule_id,
            module=mod_id,
            pack=pack,
            relevance="类型默认引用",
            reference_source="minimum_pad",
        )

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
        _append_ref(
            refs,
            seen,
            rule_id=rid,
            module=mod_id,
            pack=pack,
            relevance="调研材料引用",
            reference_source="research",
        )
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
    padded = fetch_relevant_rules(problem_type, problem_text, minimum=minimum, limit=max(minimum, 6), check_mode=None)
    seen = {r.rule_id for r in refs}
    merged = list(refs)
    for ref in padded:
        if ref.rule_id not in seen:
            merged.append(ref)
            seen.add(ref.rule_id)
        if len(merged) >= minimum:
            break
    return merged
