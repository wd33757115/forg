"""Tools for ProblemSolverAgent — bound to project state at runtime."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from forge.core.rule_pack_loader import RulePackLoader
from forge.core.state import ProjectState
from forge.tools.diagnostics import analyze_symptoms

# ---------------------------------------------------------------------------
# 等保级别要求摘要（可扩展为独立 Rule Pack 子模块）
# ---------------------------------------------------------------------------
DENGBAO_LEVEL_REQUIREMENTS: dict[str, list[dict[str, str]]] = {
    "1": [
        {"control": "基础防护", "requirement": "基本身份鉴别与访问控制"},
        {"control": "审计", "requirement": "关键操作日志记录"},
    ],
    "2": [
        {"control": "身份鉴别", "requirement": "唯一身份标识，失败登录处理，密码复杂度策略"},
        {"control": "访问控制", "requirement": "最小权限原则，默认拒绝"},
        {"control": "安全审计", "requirement": "审计记录保护，覆盖关键用户行为"},
    ],
    "3": [
        {"control": "身份鉴别", "requirement": "双因素认证（高风险场景），防暴力破解"},
        {"control": "访问控制", "requirement": "细粒度权限控制，角色分离"},
        {"control": "安全审计", "requirement": "集中审计，异常行为告警"},
        {"control": "边界防护", "requirement": "访问控制策略，入侵防范"},
        {"control": "恶意代码防范", "requirement": "主机与网络层防护"},
    ],
    "4": [
        {"control": "全部第三级要求", "requirement": "并增强"},
        {"control": "安全管理中心", "requirement": "统一安全管理、审计、核查"},
        {"control": "数据完整性", "requirement": "传输与存储完整性保护"},
    ],
    "5": [
        {"control": "全部第四级要求", "requirement": "并增强"},
        {"control": "可信验证", "requirement": "基于硬件的可信根验证"},
    ],
}

# ---------------------------------------------------------------------------
# ITIL 实践指导摘要
# ---------------------------------------------------------------------------
ITIL_PRACTICE_GUIDANCE: dict[str, dict[str, Any]] = {
    "incident": {
        "practice": "Incident Management",
        "summary": "尽快恢复服务，记录事件时间线、影响范围、优先级",
        "steps": ["记录事件", "分类分级", "调查诊断", "解决恢复", "关闭事件"],
        "iso_reference": "ISO/IEC 20000-1 8.6",
    },
    "problem": {
        "practice": "Problem Management",
        "summary": "识别根因，防止复发，与已知错误库关联",
        "steps": ["问题识别", "根因分析", "已知错误记录", "变更请求"],
        "iso_reference": "ISO/IEC 20000-1 8.7",
    },
    "change": {
        "practice": "Change Enablement",
        "summary": "评估变更风险，获得授权后实施，保留回退方案",
        "steps": ["变更请求", "影响评估", "CAB 审批", "实施验证", "回顾"],
        "iso_reference": "ISO/IEC 20000-1 8.5",
    },
    "configuration": {
        "practice": "Service Configuration Management",
        "summary": "维护 CMDB，确保配置项与实际情况一致",
        "steps": ["识别配置项", "记录关系", "变更同步", "定期审计"],
        "iso_reference": "ITIL 4 SCM",
    },
    "service_level": {
        "practice": "Service Level Management",
        "summary": "对照 SLA 评估服务影响，触发相应响应流程",
        "steps": ["确认 SLA 指标", "评估偏差", "升级路径", "客户沟通"],
        "iso_reference": "ISO/IEC 20000-1 8.3",
    },
}


class QueryRulePackInput(BaseModel):
    module: str = Field(
        default="",
        description="Module name: base_si, dengbao_2.0, or itil_iso20000. Empty = all enabled.",
    )
    category: str = Field(default="", description="Optional rule category filter")
    keyword: str = Field(default="", description="Optional keyword search in title/description")


class DengbaoLevelInput(BaseModel):
    level: str = Field(description="等保级别: 1-5", pattern=r"^[1-5]$")


class ItilPracticeInput(BaseModel):
    practice: str = Field(
        description="ITIL practice key: incident, problem, change, configuration, service_level"
    )


class AnalyzeImpactInput(BaseModel):
    problem_description: str = Field(description="Brief description of the problem to assess impact")


class SearchCasesInput(BaseModel):
    query: str = Field(description="Search query for historical cases in knowledge base")


def _get_rule_pack_bundle(state: ProjectState):
    loader = RulePackLoader.get_instance()
    return loader.load_default()


def _tool_get_current_project_state(state: ProjectState) -> str:
    """Return a JSON summary of the current Forge project state."""
    summary = {
        "project_id": state.get("project_id"),
        "current_phase": state.get("current_phase"),
        "enabled_modules": state.get("enabled_modules", []),
        "wbs_items": list(state.get("wbs", {}).keys()),
        "wbs_detail": state.get("wbs", {}),
        "document_count": len(state.get("documents", [])),
        "documents": [d.get("title", "") for d in state.get("documents", [])],
        "compliance_results_count": len(state.get("compliance_results", [])),
        "latest_compliance": state.get("compliance_results", [])[-1:]
        if state.get("compliance_results")
        else [],
        "knowledge_base_count": len(state.get("knowledge_base", [])),
        "rule_pack_id": (state.get("rule_pack") or {}).get("pack_id"),
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def _tool_query_rule_pack(state: ProjectState, module: str, category: str, keyword: str) -> str:
    """Query enabled Rule Pack modules for matching rules."""
    bundle = _get_rule_pack_bundle(state)
    enabled = state.get("enabled_modules") or bundle.get_enabled_modules()
    target_modules = [module] if module and module in enabled else list(enabled)

    results: list[dict[str, Any]] = []
    for mod_name in target_modules:
        mod = bundle.get_module(mod_name)
        if mod is None:
            continue
        rules = mod.rules
        if category:
            rules = mod.rules_by_category(category)
        if keyword:
            kw = keyword.lower()
            rules = [r for r in rules if kw in r.title.lower() or kw in r.description.lower()]
        for rule in rules:
            results.append(
                {
                    "module": mod_name,
                    "id": rule.id,
                    "title": rule.title,
                    "category": rule.category,
                    "severity": rule.severity,
                    "description": rule.description,
                    "checks": rule.checks,
                    "references": rule.references,
                }
            )
    return json.dumps(results, ensure_ascii=False, indent=2)


def _tool_get_dengbao_requirements(state: ProjectState, level: str) -> str:
    """Return 等保2.0 requirements for the given protection level (1-5)."""
    level_reqs = DENGBAO_LEVEL_REQUIREMENTS.get(level, [])
    bundle = _get_rule_pack_bundle(state)
    dengbao = bundle.get_module("dengbao_2.0")
    pack_rules = []
    if dengbao:
        pack_rules = [
            {"id": r.id, "title": r.title, "category": r.category, "references": r.references}
            for r in dengbao.rules
        ]
    payload = {
        "level": level,
        "level_requirements": level_reqs,
        "rule_pack_rules": pack_rules,
        "note": "结合项目等保定级与 Rule Pack 规则执行差距分析",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _tool_get_itil_guidance(state: ProjectState, practice: str) -> str:
    """Return ITIL/ISO20000 guidance for a specific practice area."""
    key = practice.lower().strip()
    guidance = ITIL_PRACTICE_GUIDANCE.get(key)
    if guidance is None:
        available = list(ITIL_PRACTICE_GUIDANCE.keys())
        return json.dumps(
            {"error": f"Unknown practice '{practice}'", "available": available},
            ensure_ascii=False,
        )

    bundle = _get_rule_pack_bundle(state)
    itil_mod = bundle.get_module("itil_iso20000")
    related_rules = []
    if itil_mod:
        related_rules = [
            {"id": r.id, "title": r.title, "category": r.category}
            for r in itil_mod.rules
            if key in r.category or key in r.title.lower()
        ]

    payload = {**guidance, "related_rule_pack_rules": related_rules}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _tool_analyze_impact(state: ProjectState, problem_description: str) -> str:
    """Analyze impact on WBS items, compliance posture, and project phase."""
    wbs = state.get("wbs", {})
    modules = _get_rule_pack_bundle(state).get_enabled_module_map()
    diagnosis = analyze_symptoms(problem_description, modules)

    affected_wbs: list[str] = []
    problem_lower = problem_description.lower()
    for wbs_id, item in wbs.items():
        name = item.get("name", wbs_id) if isinstance(item, dict) else str(item)
        if wbs_id.lower() in problem_lower or name.lower() in problem_lower:
            affected_wbs.append(wbs_id)

    open_compliance_gaps = 0
    for result in state.get("compliance_results", []):
        if result.get("status") != "pass":
            open_compliance_gaps += len(result.get("findings", []))

    impact = {
        "diagnosis_summary": diagnosis.summary,
        "diagnosis_tags": diagnosis.tags,
        "suggested_actions": diagnosis.actions,
        "affected_wbs": affected_wbs or ["需进一步确认影响范围"],
        "current_phase": state.get("current_phase"),
        "open_compliance_gaps": open_compliance_gaps,
        "severity_hint": "high" if open_compliance_gaps > 5 else "medium",
    }
    return json.dumps(impact, ensure_ascii=False, indent=2)


def _tool_search_historical_cases(state: ProjectState, query: str) -> str:
    """Search project knowledge base for similar historical cases."""
    query_lower = query.lower()
    matches: list[dict[str, Any]] = []
    for entry in state.get("knowledge_base", []):
        content = entry.get("content", "")
        tags = entry.get("tags", [])
        tag_str = " ".join(tags) if isinstance(tags, list) else str(tags)
        if (
            query_lower in content.lower()
            or query_lower in tag_str.lower()
            or query_lower in entry.get("category", "").lower()
        ):
            matches.append(entry)

    # Built-in seed cases when knowledge base is empty
    if not matches and not state.get("knowledge_base"):
        seed_cases = [
            {
                "id": "seed-001",
                "category": "problem_pattern",
                "content": "SSO 证书过期导致 401 — 更新证书并同步至所有集成节点",
                "tags": ["auth", "integration"],
            },
            {
                "id": "seed-002",
                "category": "problem_pattern",
                "content": "等保审计缺少安全审计日志 — 启用集中日志并保留 6 个月以上",
                "tags": ["dengbao", "audit"],
            },
        ]
        matches = [
            c for c in seed_cases if query_lower in c["content"].lower() or query_lower in " ".join(c["tags"])
        ]

    return json.dumps(matches[:5], ensure_ascii=False, indent=2)


def build_problem_solver_tools(state: ProjectState) -> list[BaseTool]:
    """
    Build LangChain tools bound to the current ProjectState.

    Tools are recreated per invocation so they always see fresh state.
    """

    def get_current_project_state() -> str:
        """Get current Forge project state summary including WBS, phase, and compliance."""
        return _tool_get_current_project_state(state)

    def query_rule_pack(
        module: str = "",
        category: str = "",
        keyword: str = "",
    ) -> str:
        """Query Rule Pack rules by module (base_si/dengbao_2.0/itil_iso20000), category, or keyword."""
        return _tool_query_rule_pack(state, module, category, keyword)

    def get_dengbao_requirements(level: str) -> str:
        """Get 等保2.0 requirements for protection level 1-5, combined with Rule Pack rules."""
        return _tool_get_dengbao_requirements(state, level)

    def get_itil_guidance(practice: str) -> str:
        """Get ITIL/ISO20000 guidance for incident, problem, change, configuration, or service_level."""
        return _tool_get_itil_guidance(state, practice)

    def analyze_impact(problem_description: str) -> str:
        """Analyze problem impact on WBS, compliance gaps, and project phase."""
        return _tool_analyze_impact(state, problem_description)

    def search_historical_cases(query: str) -> str:
        """Search knowledge base for similar historical problem cases."""
        return _tool_search_historical_cases(state, query)

    return [
        StructuredTool.from_function(
            func=get_current_project_state,
            name="get_current_project_state",
            description=get_current_project_state.__doc__ or "",
        ),
        StructuredTool.from_function(
            func=query_rule_pack,
            name="query_rule_pack",
            description=query_rule_pack.__doc__ or "",
            args_schema=QueryRulePackInput,
        ),
        StructuredTool.from_function(
            func=get_dengbao_requirements,
            name="get_dengbao_requirements",
            description=get_dengbao_requirements.__doc__ or "",
            args_schema=DengbaoLevelInput,
        ),
        StructuredTool.from_function(
            func=get_itil_guidance,
            name="get_itil_guidance",
            description=get_itil_guidance.__doc__ or "",
            args_schema=ItilPracticeInput,
        ),
        StructuredTool.from_function(
            func=analyze_impact,
            name="analyze_impact",
            description=analyze_impact.__doc__ or "",
            args_schema=AnalyzeImpactInput,
        ),
        StructuredTool.from_function(
            func=search_historical_cases,
            name="search_historical_cases",
            description=search_historical_cases.__doc__ or "",
            args_schema=SearchCasesInput,
        ),
    ]


def run_tool_research(
    state: ProjectState,
    problem_statement: str,
    *,
    problem_type: str | None = None,
) -> str:
    """
    Execute tools programmatically (heuristic / ReAct fallback).

    When ``problem_type`` is set, prioritizes relevant Rule Pack modules and
    ITIL/等保 lookups (security → dengbao, service_management → itil, etc.).
    """
    from forge.agents.problem_classifier import ProblemType, classify_problem, modules_for_problem_type

    hint = problem_type or state.get("problem_type") or state.get("problem_type_hint")
    resolved_type: ProblemType
    type_reason: str
    if problem_type:
        resolved_type = problem_type  # type: ignore[assignment]
        type_reason = "explicit"
    else:
        resolved_type, type_reason, _conf = classify_problem(problem_statement, hint=hint)

    level = str((state.get("rule_pack") or {}).get("protection_level", "3"))
    modules = modules_for_problem_type(resolved_type)

    sections: list[tuple[str, str]] = [
        ("project_state", _tool_get_current_project_state(state)),
        ("problem_type", f"{resolved_type} — {type_reason}"),
        ("impact", _tool_analyze_impact(state, problem_statement)),
        ("historical_cases", _tool_search_historical_cases(state, problem_statement)),
    ]

    for mod in modules:
        sections.append((f"rule_pack_{mod}", _tool_query_rule_pack(state, mod, "", "")))

    if resolved_type in ("security", "mixed") or "dengbao" in modules:
        sections.append((f"dengbao_l{level}", _tool_get_dengbao_requirements(state, level)))

    if resolved_type in ("service_management", "mixed"):
        for practice in ("incident", "problem", "change"):
            sections.append(
                (f"itil_{practice}", _tool_get_itil_guidance(state, practice)),
            )
    elif resolved_type == "technical":
        sections.append(("itil_incident", _tool_get_itil_guidance(state, "incident")))

    if not any(n.startswith("rule_pack_") for n, _ in sections):
        sections.insert(1, ("rule_pack_all", _tool_query_rule_pack(state, "", "", "")))

    return "\n\n".join(f"### {name}\n{content}" for name, content in sections)
