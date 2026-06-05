"""Problem type classification for ProblemSolverAgent."""

from __future__ import annotations

from typing import Literal

ProblemType = Literal["security", "service_management", "technical", "mixed"]

PROBLEM_TYPE_LABELS: dict[ProblemType, str] = {
    "security": "安全类（等保/身份/边界/审计）",
    "service_management": "服务管理类（ITIL/事件/变更/SLA）",
    "technical": "技术类（性能/集成/架构/故障）",
    "mixed": "混合类（安全 + 服务管理 + 技术交叉）",
}

# Keyword sets for heuristic classification
_SECURITY_KW = (
    "等保", "安全", "测评", "401", "403", "认证", "登录", "auth", "防火墙",
    "审计", "渗透", "漏洞", "加固", "边界", "加密", "dengbao", "security",
)
_ITIL_KW = (
    "itil", "事件", "incident", "sla", "变更", "cab", "cmdb", "服务台",
    "工单", "运维", "中断", "宕机", "outage", "服务级别", "问题管理",
)
_TECH_KW = (
    "超时", "timeout", "慢", "性能", "连接池", "接口", "数据库", "集成",
    "报错", "异常", "error", "故障", "根因", "latency", "架构",
)


def classify_problem(text: str, *, hint: str | None = None) -> tuple[ProblemType, str]:
    """
    Classify user problem into security / service_management / technical / mixed.

    Returns (problem_type, human-readable reasoning).
    """
    if hint:
        hint_map: dict[str, ProblemType] = {
            "security": "security",
            "itil": "service_management",
            "operations": "service_management",
            "service_management": "service_management",
            "general": "technical",
            "technical": "technical",
            "mixed": "mixed",
        }
        if hint in hint_map:
            ptype = hint_map[hint]
            return ptype, f"CLI 指定类型: {PROBLEM_TYPE_LABELS[ptype]}"

    lower = text.lower()
    is_sec = any(k in lower for k in _SECURITY_KW)
    is_itil = any(k in lower for k in _ITIL_KW)
    is_tech = any(k in lower for k in _TECH_KW)

    if is_sec and is_itil:
        return "mixed", "同时命中等保/安全与服务管理（ITIL）关键词"
    if is_sec and is_tech and not is_itil:
        return "mixed", "同时命中安全与技术故障关键词"
    if is_sec:
        return "security", "命中等保/安全控制相关关键词"
    if is_itil:
        return "service_management", "命中 ITIL/事件/变更/SLA 关键词"
    if is_tech:
        return "technical", "命中性能/集成/技术故障关键词"
    return "technical", "未命中明确分类关键词，默认按技术问题处理"


def modules_for_problem_type(problem_type: ProblemType) -> list[str]:
    """Suggest Rule Pack modules to prioritize for a problem type."""
    if problem_type == "security":
        return ["dengbao_2.0", "base_si"]
    if problem_type == "service_management":
        return ["itil_iso20000", "base_si"]
    if problem_type == "mixed":
        return ["dengbao_2.0", "itil_iso20000", "base_si"]
    return ["base_si", "dengbao_2.0", "itil_iso20000"]
