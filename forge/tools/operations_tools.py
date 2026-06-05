"""OperationsAgent tools — itil_iso20000 focused."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from forge.core.rule_pack_loader import RulePackLoader
from forge.core.state import ProjectState
from forge.tools.problem_solver_tools import ITIL_PRACTICE_GUIDANCE

CHANGE_PROCESS_TEMPLATE: dict[str, Any] = {
    "standard": {
        "description": "预授权、低风险、可重复变更",
        "steps": ["记录变更", "实施", "验证", "关闭"],
    },
    "normal": {
        "description": "需评估与 CAB 审批的常规变更",
        "steps": ["RFC 提交", "影响评估", "CAB 审批", "实施窗口", "验证", "回顾"],
    },
    "emergency": {
        "description": "紧急变更，事后补审",
        "steps": ["紧急授权", "实施", "验证", "事后 CAB 补审", "事件关联"],
    },
}


class ItilPracticeInput(BaseModel):
    practice: str = Field(
        default="incident",
        description="incident | problem | change | configuration | service_level",
    )


class IncidentImpactInput(BaseModel):
    description: str = Field(description="Incident or service disruption description")


def _tool_query_itil_rules(state: ProjectState) -> str:
    bundle = RulePackLoader.get_instance().load_default()
    itil = bundle.get_module("itil_iso20000")
    if not itil:
        return json.dumps({"error": "itil_iso20000 module not loaded"}, ensure_ascii=False)
    rules = [
        {
            "id": r.id,
            "title": r.title,
            "category": r.category,
            "severity": r.severity,
            "description": r.description,
            "checks": r.checks,
            "references": r.references,
        }
        for r in itil.rules
    ]
    return json.dumps(rules, ensure_ascii=False, indent=2)


def _tool_get_itil_practice_guidance(state: ProjectState, practice: str) -> str:
    guidance = ITIL_PRACTICE_GUIDANCE.get(practice)
    if not guidance:
        return json.dumps(
            {"error": f"unknown practice: {practice}", "available": list(ITIL_PRACTICE_GUIDANCE)},
            ensure_ascii=False,
        )
    return json.dumps(guidance, ensure_ascii=False, indent=2)


def _tool_analyze_incident_impact(state: ProjectState, description: str) -> str:
    desc_lower = description.lower()
    priority = "P3"
    impact = "局部影响"
    if any(k in desc_lower for k in ("中断", "宕机", "down", "outage", "核心")):
        priority = "P1"
        impact = "核心业务中断"
    elif any(k in desc_lower for k in ("超时", "慢", "降级")):
        priority = "P2"
        impact = "服务性能降级"

    payload = {
        "description": description,
        "suggested_priority": priority,
        "impact": impact,
        "escalation": "15 分钟内通知服务负责人" if priority == "P1" else "按 SLA 升级矩阵",
        "related_practices": ["incident", "problem", "service_level"],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _tool_get_change_process_template(state: ProjectState) -> str:
    return json.dumps(CHANGE_PROCESS_TEMPLATE, ensure_ascii=False, indent=2)


def _tool_suggest_knowledge_entries(state: ProjectState) -> str:
    solution = state.get("last_solution") or {}
    entries = []
    for rc in solution.get("root_causes", [])[:3]:
        entries.append(f"已知错误候选：{rc} — 记录根因、临时规避与永久修复")
    if solution.get("recommended_solution_id"):
        entries.append(
            f"方案知识条目：{solution.get('recommended_solution_id')} — "
            "记录实施步骤与验证方法"
        )
    if not entries:
        entries = [
            "事件处理记录模板：时间线、影响、处置、验证",
            "问题记录模板：根因、永久修复、关联变更",
        ]
    return json.dumps({"suggested_entries": entries}, ensure_ascii=False, indent=2)


def _tool_get_solution_context(state: ProjectState) -> str:
    solution = state.get("last_solution")
    if not solution:
        return "（暂无 ProblemSolver 方案）"
    return json.dumps(
        {
            "problem_analysis": solution.get("problem_analysis", ""),
            "root_causes": solution.get("root_causes", []),
            "recommended_solution_id": solution.get("recommended_solution_id"),
            "next_actions": solution.get("next_actions", []),
            "itil_considerations": solution.get("itil_considerations", ""),
        },
        ensure_ascii=False,
        indent=2,
    )


def build_operations_tools(state: ProjectState) -> list[BaseTool]:
    def query_itil_rules() -> str:
        return _tool_query_itil_rules(state)

    def get_itil_practice_guidance(practice: str = "incident") -> str:
        return _tool_get_itil_practice_guidance(state, practice)

    def analyze_incident_impact(description: str) -> str:
        return _tool_analyze_incident_impact(state, description)

    def get_change_process_template() -> str:
        return _tool_get_change_process_template(state)

    def suggest_knowledge_entries() -> str:
        return _tool_suggest_knowledge_entries(state)

    def get_solution_context() -> str:
        return _tool_get_solution_context(state)

    return [
        StructuredTool.from_function(
            func=query_itil_rules,
            name="query_itil_rules",
            description="查询 itil_iso20000 Rule Pack 流程规则",
        ),
        StructuredTool.from_function(
            func=get_itil_practice_guidance,
            name="get_itil_practice_guidance",
            description="按 ITIL 实践域获取流程指导",
            args_schema=ItilPracticeInput,
        ),
        StructuredTool.from_function(
            func=analyze_incident_impact,
            name="analyze_incident_impact",
            description="分析事件影响与建议优先级",
            args_schema=IncidentImpactInput,
        ),
        StructuredTool.from_function(
            func=get_change_process_template,
            name="get_change_process_template",
            description="获取变更管理流程模板",
        ),
        StructuredTool.from_function(
            func=suggest_knowledge_entries,
            name="suggest_knowledge_entries",
            description="建议知识库沉淀条目",
        ),
        StructuredTool.from_function(
            func=get_solution_context,
            name="get_solution_context",
            description="读取 ProblemSolver 方案上下文",
        ),
    ]


def run_operations_research(state: ProjectState, context: str) -> str:
    """Offline fallback: run all operations tools programmatically."""
    practice = "incident"
    if any(k in context.lower() for k in ("变更", "change")):
        practice = "change"
    elif any(k in context.lower() for k in ("问题", "根因", "problem")):
        practice = "problem"

    sections = [
        ("## itil_iso20000 规则", _tool_query_itil_rules(state)),
        ("## ITIL 实践指导", _tool_get_itil_practice_guidance(state, practice)),
        ("## 事件影响", _tool_analyze_incident_impact(state, context)),
        ("## 变更流程", _tool_get_change_process_template(state)),
        ("## 知识库建议", _tool_suggest_knowledge_entries(state)),
        ("## 方案上下文", _tool_get_solution_context(state)),
        ("## 用户上下文", context),
    ]
    return "\n\n".join(f"{title}\n{body}" for title, body in sections)
