"""SecurityAgent tools — dengbao_2.0 focused."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from forge.core.rule_pack_loader import RulePackLoader
from forge.core.state import ProjectState
from forge.tools.compliance_tools import check_dengbao_compliance
from forge.tools.problem_solver_tools import DENGBAO_LEVEL_REQUIREMENTS

SECURITY_CONFIG_TEMPLATES: dict[str, dict[str, Any]] = {
    "firewall": {
        "title": "边界防火墙策略",
        "items": [
            "默认拒绝策略，仅开放业务必需端口",
            "南北向流量与应用层检测",
            "策略变更需审批并留存记录",
        ],
        "dengbao_ref": "db-bnd-001",
    },
    "audit": {
        "title": "安全审计与日志",
        "items": [
            "集中日志采集与 6 个月以上留存",
            "管理员操作全量审计",
            "异常登录与权限变更告警",
        ],
        "dengbao_ref": "db-aud-001",
    },
    "access_control": {
        "title": "访问控制",
        "items": [
            "最小权限与角色分离",
            "双因素认证（三级及以上高风险场景）",
            "定期账号与权限复核",
        ],
        "dengbao_ref": "db-acs-001",
    },
}


class DengbaoLevelInput(BaseModel):
    level: str = Field(default="3", description="等保保护级别 1-5", pattern=r"^[1-5]$")


class SecurityRiskInput(BaseModel):
    context: str = Field(description="Brief security issue or scenario to assess")


def _get_protection_level(state: ProjectState) -> str:
    rule_pack = state.get("rule_pack") or {}
    return str(rule_pack.get("protection_level", "3"))


def _tool_query_dengbao_rules(state: ProjectState) -> str:
    bundle = RulePackLoader.get_instance().load_default()
    dengbao = bundle.get_module("dengbao_2.0")
    if not dengbao:
        return json.dumps({"error": "dengbao_2.0 module not loaded"}, ensure_ascii=False)
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
        for r in dengbao.rules
    ]
    return json.dumps(rules, ensure_ascii=False, indent=2)


def _tool_get_dengbao_requirements(state: ProjectState, level: str) -> str:
    level_reqs = DENGBAO_LEVEL_REQUIREMENTS.get(level, [])
    bundle = RulePackLoader.get_instance().load_default()
    dengbao = bundle.get_module("dengbao_2.0")
    pack_rules = []
    if dengbao:
        pack_rules = [
            {"id": r.id, "title": r.title, "category": r.category}
            for r in dengbao.rules
        ]
    payload = {
        "protection_level": level,
        "level_requirements": level_reqs,
        "rule_pack_rules": pack_rules,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _tool_check_dengbao_gaps(state: ProjectState) -> str:
    level = _get_protection_level(state)
    result = check_dengbao_compliance(state, level)
    return json.dumps(result, ensure_ascii=False, indent=2)


def _tool_get_security_config_templates(state: ProjectState) -> str:
    level = _get_protection_level(state)
    payload = {
        "protection_level": level,
        "templates": SECURITY_CONFIG_TEMPLATES,
        "note": "三级及以上需强化审计集中化与边界防护策略",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _tool_analyze_security_risk(state: ProjectState, context: str) -> str:
    solution = state.get("last_solution") or {}
    compliance = state.get("last_compliance_result") or {}
    context_lower = context.lower()

    risks: list[dict[str, str]] = []
    if any(k in context_lower for k in ("401", "403", "认证", "登录", "auth")):
        risks.append(
            {
                "title": "身份鉴别风险",
                "severity": "high",
                "detail": "认证失败可能导致未授权访问或审计缺口",
            }
        )
    if any(k in context_lower for k in ("防火墙", "边界", "网络")):
        risks.append(
            {
                "title": "边界防护风险",
                "severity": "medium",
                "detail": "边界策略不当可能导致横向移动",
            }
        )
    if compliance.get("compliance_status") == "non_compliant":
        risks.append(
            {
                "title": "等保合规缺口",
                "severity": compliance.get("risk_level", "high"),
                "detail": f"存在 {len(compliance.get('missing_items', []))} 项缺口",
            }
        )
    if not risks:
        risks.append(
            {
                "title": "待评估安全风险",
                "severity": "medium",
                "detail": "需结合现场配置与测评项进一步确认",
            }
        )

    payload = {
        "context": context,
        "recommended_solution": solution.get("recommended_solution_id"),
        "risks": risks,
        "protection_level": _get_protection_level(state),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


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
            "dengbao_considerations": solution.get("dengbao_considerations", ""),
        },
        ensure_ascii=False,
        indent=2,
    )


def build_security_tools(state: ProjectState) -> list[BaseTool]:
    def query_dengbao_rules() -> str:
        return _tool_query_dengbao_rules(state)

    def get_dengbao_requirements(level: str = "3") -> str:
        return _tool_get_dengbao_requirements(state, level)

    def check_dengbao_gaps() -> str:
        return _tool_check_dengbao_gaps(state)

    def get_security_config_templates() -> str:
        return _tool_get_security_config_templates(state)

    def analyze_security_risk(context: str) -> str:
        return _tool_analyze_security_risk(state, context)

    def get_solution_context() -> str:
        return _tool_get_solution_context(state)

    return [
        StructuredTool.from_function(
            func=query_dengbao_rules,
            name="query_dengbao_rules",
            description="查询 dengbao_2.0 Rule Pack 等保规则",
        ),
        StructuredTool.from_function(
            func=get_dengbao_requirements,
            name="get_dengbao_requirements",
            description="按保护级别获取等保2.0要求",
            args_schema=DengbaoLevelInput,
        ),
        StructuredTool.from_function(
            func=check_dengbao_gaps,
            name="check_dengbao_gaps",
            description="检查当前项目等保合规缺口",
        ),
        StructuredTool.from_function(
            func=get_security_config_templates,
            name="get_security_config_templates",
            description="获取防火墙/审计/访问控制配置建议模板",
        ),
        StructuredTool.from_function(
            func=analyze_security_risk,
            name="analyze_security_risk",
            description="评估安全场景风险",
            args_schema=SecurityRiskInput,
        ),
        StructuredTool.from_function(
            func=get_solution_context,
            name="get_solution_context",
            description="读取 ProblemSolver 方案上下文",
        ),
    ]


def run_security_research(state: ProjectState, context: str) -> str:
    """Offline fallback: run all security tools programmatically."""
    sections = [
        ("## dengbao_2.0 规则", _tool_query_dengbao_rules(state)),
        ("## 等保要求", _tool_get_dengbao_requirements(state, _get_protection_level(state))),
        ("## 等保缺口", _tool_check_dengbao_gaps(state)),
        ("## 安全配置模板", _tool_get_security_config_templates(state)),
        ("## 风险评估", _tool_analyze_security_risk(state, context)),
        ("## 方案上下文", _tool_get_solution_context(state)),
        ("## 用户上下文", context),
    ]
    return "\n\n".join(f"{title}\n{body}" for title, body in sections)
