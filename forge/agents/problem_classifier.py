"""Problem type classification for ProblemSolverAgent.

Maps user questions to internal ProblemType values. CLI aliases:
  security → security
  itil     → service_management
  general  → technical
"""

from __future__ import annotations

from typing import Literal

ProblemType = Literal["security", "service_management", "technical", "mixed"]

PROBLEM_TYPE_LABELS: dict[ProblemType, str] = {
    "security": "安全类（等保/身份/边界/审计）— CLI: security",
    "service_management": "服务管理类（ITIL/事件/变更/SLA）— CLI: itil",
    "technical": "技术类（性能/集成/架构/故障）— CLI: general",
    "mixed": "混合类（安全 + 服务管理 + 技术交叉）",
}

# Heuristic keyword sets (ordered by specificity)
_SECURITY_STRONG = ("401", "403", "等保", "测评", "身份鉴别", "认证", "登录", "auth", "dengbao")
_SECURITY_KW = _SECURITY_STRONG + (
    "安全", "防火墙", "审计", "渗透", "漏洞", "加固", "边界", "加密", "security",
)
_ITIL_STRONG = ("itil", "sla", "cab", "cmdb", "incident", "outage")
_ITIL_KW = _ITIL_STRONG + (
    "事件", "变更", "服务台", "工单", "运维", "中断", "宕机", "服务级别", "问题管理",
)
_TECH_STRONG = ("连接池", "timeout", "latency", "慢查询", "接口超时")
_TECH_KW = _TECH_STRONG + (
    "超时", "慢", "性能", "接口", "数据库", "集成", "报错", "异常", "error", "架构",
)
# Generic words that should not alone trigger mixed with security
_TECH_GENERIC = ("故障", "根因", "问题")


def _score(text: str, keywords: tuple[str, ...], *, strong: tuple[str, ...] = ()) -> int:
    """Count keyword hits; strong indicators count double."""
    lower = text.lower()
    score = 0
    for kw in keywords:
        if kw in lower:
            score += 3 if kw in strong else 1
    return score


def classify_problem(text: str, *, hint: str | None = None) -> tuple[ProblemType, str, float]:
    """
    Classify user problem into security / service_management / technical / mixed.

    Returns (problem_type, human-readable reasoning, classification_confidence 0.0-1.0).

    D4 enhancements:
    - Returns explicit confidence based on score strength and margin.
    - On uncertain signals (low max score or small margin between top domains),
      forces "mixed" and returns lower confidence. This triggers wider specialist
      routing and more thorough investigation (more tools / modules) downstream.
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
            return ptype, f"CLI 指定类型: {PROBLEM_TYPE_LABELS[ptype]}", 0.95

    lower = text.lower()
    sec = _score(lower, _SECURITY_KW, strong=_SECURITY_STRONG)
    itil = _score(lower, _ITIL_KW, strong=_ITIL_STRONG)
    tech = _score(lower, _TECH_KW, strong=_TECH_STRONG)
    tech_generic = sum(1 for k in _TECH_GENERIC if k in lower)

    if tech == 0 and tech_generic:
        tech = tech_generic

    has_sec_strong = any(k in lower for k in _SECURITY_STRONG)
    has_outage = any(k in lower for k in ("中断", "宕机", "交换机", "outage", "sla"))

    # Explicit mixed trigger (high confidence when clear overlap)
    if has_sec_strong and (itil >= 1 or has_outage):
        return "mixed", f"安全控制与运维中断并存（安全={sec}, ITIL={itil}）", 0.85

    # Dual-domain → mixed
    domains = sum(1 for s in (sec, itil, tech) if s >= 2)
    if domains >= 2:
        return "mixed", f"多域关键词并存（安全={sec}, ITIL={itil}, 技术={tech}）", 0.80

    # Determine winner and raw scores
    scores = {"security": sec, "service_management": itil, "technical": tech}
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    winner, win_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    margin = win_score - second_score
    max_score = win_score

    # Uncertainty heuristic (D4): weak overall signal or tiny margin → force mixed + lower conf
    uncertain = (max_score < 2) or (margin <= 1 and max_score < 4)
    if uncertain and winner != "mixed":
        # Force mixed to pull broader specialists and tools; confidence reflects weakness
        conf = round(max(0.35, min(0.55, (max_score + margin) / 10.0)), 2)
        return "mixed", f"信号较弱或域间差异小（max={max_score}, margin={margin}），不确定时走 mixed 以扩大调查范围", conf

    # Single-domain winners
    if sec >= 2 and sec >= itil and sec >= tech:
        conf = round(min(0.98, 0.55 + (sec - 1) * 0.12 + (margin * 0.05)), 2)
        return "security", f"等保/安全关键词得分最高（{sec}）", conf
    if itil >= 2 and itil >= sec and itil >= tech:
        conf = round(min(0.98, 0.55 + (itil - 1) * 0.12 + (margin * 0.05)), 2)
        return "service_management", f"ITIL/运维关键词得分最高（{itil}）", conf
    if tech >= 1 and tech >= sec and tech >= itil:
        conf = round(min(0.92, 0.50 + (tech - 1) * 0.10 + (margin * 0.04)), 2)
        return "technical", f"技术故障关键词得分最高（{tech}）", conf
    if sec >= 1:
        conf = round(0.45 + sec * 0.08, 2)
        return "security", "命中等保/安全控制相关关键词", conf
    if itil >= 1:
        conf = round(0.45 + itil * 0.08, 2)
        return "service_management", "命中 ITIL/事件/变更/SLA 关键词", conf

    # Default technical, but mark as low confidence (true unknown)
    return "technical", "未命中明确分类关键词，默认按通用技术问题（general）处理", 0.40


def classify_with_cli_hint(
    text: str,
    hint: str | None,
) -> tuple[ProblemType, str, dict[str, str] | None, float]:
    """
    Classify using CLI hint when present.

    Returns (ptype, reason, conflict_dict_or_None, classification_confidence).

    D4: now propagates classification confidence (third value from classify_problem).
    """
    if not hint:
        ptype, reason, conf = classify_problem(text)
        return ptype, reason, None, conf

    hinted, reason, conf = classify_problem(text, hint=hint)
    auto, auto_reason, _auto_conf = classify_problem(text, hint=None)
    if auto == hinted:
        return hinted, reason, None, conf

    return hinted, reason, {
        "hint": hint,
        "hinted_type": hinted,
        "auto_type": auto,
        "hint_reason": reason,
        "auto_reason": auto_reason,
        "warning": (
            f"CLI --type={hint} 映射为 {hinted}，"
            f"但自动分类为 {auto}（{auto_reason}）"
        ),
    }, conf


def modules_for_problem_type(problem_type: ProblemType) -> list[str]:
    """Suggest Rule Pack modules to prioritize for a problem type."""
    if problem_type == "security":
        return ["dengbao_2.0", "base_si"]
    if problem_type == "service_management":
        return ["itil_iso20000", "base_si"]
    if problem_type == "mixed":
        return ["dengbao_2.0", "itil_iso20000", "base_si"]
    return ["base_si", "dengbao_2.0", "itil_iso20000"]
