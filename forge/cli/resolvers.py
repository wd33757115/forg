"""CLI argument resolution helpers."""

from __future__ import annotations

import argparse

from forge.cli.scenarios import SCENARIO_LABELS, SCENARIO_QUESTIONS, TYPE_ALIASES
from forge.core.supervisor import Supervisor
from forge.utils.llm import resolve_llm_config
from forge.utils.state_persistence import default_state_path

TYPE_LABELS = {
    "security": "等保/安全 (security)",
    "itil": "ITIL/服务管理 (itil)",
    "general": "通用技术 (general)",
}

EXAMPLE_QUESTIONS = list(SCENARIO_QUESTIONS.values())


def detect_scenario_label(question: str) -> str:
    """Infer demo scenario from question keywords."""
    sup = Supervisor()
    lower = question.lower()
    if sup._is_security_intent(lower) and sup._is_operations_intent(lower):
        return SCENARIO_LABELS["mixed"]
    if sup._is_security_intent(lower) and sup._is_problem_intent(lower):
        return SCENARIO_LABELS["security"]
    if sup._is_operations_intent(lower) and sup._is_problem_intent(lower):
        return SCENARIO_LABELS["operations"]
    if sup._is_security_intent(lower):
        return "等保/安全审计"
    if sup._is_operations_intent(lower):
        return "ITIL/运维咨询"
    if sup._is_problem_intent(lower):
        return SCENARIO_LABELS["general"]
    return "综合场景"


def prompt_question() -> str:
    from forge.cli.ansi import bold, cyan, dim

    print(dim("选择场景后将自动运行完整 Agent 流水线\n"))
    print(bold("场景:"))
    keys = list(SCENARIO_LABELS.keys())
    for i, key in enumerate(keys, 1):
        label = SCENARIO_LABELS[key]
        q = SCENARIO_QUESTIONS[key]
        print(f"  {cyan(str(i))}/{cyan(key)} — [{label}] {q[:36]}…")
    print(f"  {cyan('0')} — 自定义输入")
    print()
    choice = input("请输入场景 (security/operations/mixed/general) 或编号: ").strip().lower()
    key_map = {str(i + 1): k for i, k in enumerate(keys)}
    if choice in key_map:
        return SCENARIO_QUESTIONS[key_map[choice]]
    if choice in SCENARIO_QUESTIONS:
        return SCENARIO_QUESTIONS[choice]
    if choice == "0" or not choice:
        return input("\n请输入问题: ").strip()
    return choice


def resolve_type_hint(args: argparse.Namespace) -> str | None:
    if getattr(args, "type", None):
        return TYPE_ALIASES.get(args.type, args.type)
    return None


def resolve_question(args: argparse.Namespace) -> str | None:
    type_hint = resolve_type_hint(args)
    if type_hint and type_hint in SCENARIO_QUESTIONS and not args.question:
        if args.type == "itil":
            return SCENARIO_QUESTIONS["operations"]
        return SCENARIO_QUESTIONS.get(type_hint) or SCENARIO_QUESTIONS["general"]
    if args.scenario:
        key = args.scenario
        if key == "operations":
            key = "itil"
        return SCENARIO_QUESTIONS.get(key) or SCENARIO_QUESTIONS["general"]
    if args.example:
        return EXAMPLE_QUESTIONS[args.example - 1]
    if args.interactive:
        return prompt_question()
    return args.question


def resolve_state_path(args: argparse.Namespace) -> str | None:
    if getattr(args, "load", None):
        return args.load if args.load != "auto" else str(default_state_path(args.project_id))
    if args.load_state:
        return args.load_state
    if args.resume:
        return args.resume if args.resume != "auto" else str(default_state_path(args.project_id))
    return None


def llm_status_line() -> str:
    cfg = resolve_llm_config()
    if cfg is None:
        return "未配置 API Key（启发式离线模式）"
    return f"{cfg.provider} / {cfg.model} (重试≤{cfg.max_retries})"
