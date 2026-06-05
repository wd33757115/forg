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
        question="等保三级登录401认证失败，请诊断根因并给出技术处置建议",
        description="等保 / 身份鉴别场景（触发 ProblemSolver 闭环）",
    ),
    "itil": DemoScenario(
        id="itil",
        problem_type_hint="itil",
        question="ITIL事件：核心交换机故障导致业务中断与SLA违约，请诊断并给出处置建议",
        description="ITIL 事件 / SLA 场景（触发 ProblemSolver 闭环）",
    ),
    "mixed": DemoScenario(
        id="mixed",
        problem_type_hint="mixed",
        question="等保401认证失败同时核心交换机故障中断，请综合诊断根因",
        description="安全 + 运维混合场景（触发 ProblemSolver 闭环）",
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
