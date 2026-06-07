"""Predefined demo scenarios for Forge CLI (M3)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoScenario:
    """A runnable demo preset."""

    id: str
    problem_type_hint: str
    question: str
    description: str


# Legacy keys used by main.py interactive CLI
SCENARIO_LABELS: dict[str, str] = {
    "security": "等保/安全问题",
    "operations": "ITIL/运维事件",
    "mixed": "等保+ITIL混合问题",
    "general": "普通技术问题",
}

TYPE_ALIASES: dict[str, str] = {
    "security": "security",
    "itil": "operations",
    "operations": "operations",
    "general": "general",
    "mixed": "mixed",
}

DEMO_SCENARIOS: dict[str, DemoScenario] = {
    "security": DemoScenario(
        id="security",
        problem_type_hint="security",
        question=(
            "等保三级系统登录接口持续返回 401，审计日志显示认证失败激增。"
            "请对照 dengbao_2.0 身份鉴别控制项诊断根因，给出可执行处置方案并引用具体 rule_id。"
        ),
        description="等保 / 身份鉴别（db-acs 系列 Rule Pack 引用 + 合规闭环）",
    ),
    "itil": DemoScenario(
        id="itil",
        problem_type_hint="itil",
        question=(
            "P1 ITIL 事件：核心交换机故障导致多业务中断，SLA 已违约。"
            "请按 itil-inc / itil-slm 流程给出事件分级、升级路径与恢复步骤，并引用 rule_id。"
        ),
        description="ITIL 事件 / SLA（itil_iso20000 Rule Pack + 合规校验）",
    ),
    "mixed": DemoScenario(
        id="mixed",
        problem_type_hint="mixed",
        question=(
            "等保三级登录 401 认证失败与核心交换机故障同时发生，安全审计与服务可用性均受影响。"
            "请联合 dengbao_2.0 与 itil_iso20000 双轨诊断，给出联合应急方案并引用 ≥3 条 rule_id。"
        ),
        description="等保 + ITIL 混合（双模块 Rule Pack + handoff 到 Compliance）",
    ),
    "general": DemoScenario(
        id="general",
        problem_type_hint="general",
        question="数据库连接池耗尽导致接口超时故障，请诊断并给出技术处置建议",
        description="通用技术问题（触发 ProblemSolver 闭环）",
    ),
}

SCENARIO_QUESTIONS: dict[str, str] = {k: v.question for k, v in DEMO_SCENARIOS.items()}
# Legacy interactive key used by SCENARIO_LABELS
SCENARIO_QUESTIONS["operations"] = DEMO_SCENARIOS["itil"].question


def get_scenario(name: str) -> DemoScenario | None:
    """Resolve scenario by id or alias."""
    key = name.lower().strip()
    aliases = {
        "itil": "itil",
        "operations": "itil",
        "service_management": "itil",
        "sec": "security",
        "general": "security",
    }
    resolved = aliases.get(key, key)
    return DEMO_SCENARIOS.get(resolved)
