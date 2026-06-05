"""Forge CLI — command-line interface for the multi-agent project pipeline."""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
import traceback
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage

from forge.core import compile_workflow, create_initial_state
from forge.core.state import ProjectState
from forge.core.supervisor import Supervisor
from forge.utils.env import load_dotenv
from forge.utils.logger import get_logger, setup_logging
from forge.utils.state_persistence import (
    default_state_path,
    list_saved_states,
    load_state,
    load_state_with_metadata,
    prepare_state_for_run,
    save_state,
)

# ---------------------------------------------------------------------------
# Terminal styling (disabled when NO_COLOR is set)
# ---------------------------------------------------------------------------
_USE_COLOR = not os.environ.get("NO_COLOR")

CLI_EPILOG = """
示例:
  # 等保安全场景
  py main.py --scenario security

  # ITIL 运维场景
  py main.py --scenario operations

  # 自定义问题
  py main.py "等保三级登录401故障，请诊断"

  # 交互式选择场景
  py main.py -i

  # 保存 / 恢复项目状态
  py main.py --scenario general --save-state
  py main.py --resume --scenario security
  py main.py --load-state .forge_state/cli-demo.json --inspect

  # 列出已保存状态
  py main.py --list-states

  # 启动 Web 服务
  py main.py --web
  uvicorn web.app:app --reload

Windows 提示: 请使用 py main.py 或 .\\run.bat，勿用商店占位符 python。
"""


def _configure_stdio() -> None:
    """Prefer UTF-8 stdout/stderr (Windows default GBK cannot encode • ✓ → etc.)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(t: str) -> str:
    return _c("1", t)


def cyan(t: str) -> str:
    return _c("36", t)


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def red(t: str) -> str:
    return _c("31", t)


def dim(t: str) -> str:
    return _c("2", t)


def banner() -> None:
    print()
    print(bold("╔══════════════════════════════════════════════════════════════╗"))
    print(bold("║") + cyan("   Forge — 项目级 AI 操作系统") + bold("                              ║"))
    print(
        bold("║")
        + dim("   ProblemSolver → Security/Ops → Compliance → Document → PM")
        + bold("   ║")
    )
    print(bold("╚══════════════════════════════════════════════════════════════╝"))
    print()


def section(title: str) -> None:
    width = 62
    print()
    print(bold(f"┌─ {title} " + "─" * max(0, width - len(title) - 4)))


def _wrap(text: str, indent: int = 2) -> str:
    prefix = " " * indent
    return textwrap.fill(text, width=76, initial_indent=prefix, subsequent_indent=prefix)


SCENARIO_QUESTIONS = {
    "security": "等保三级系统登录认证失败返回401，请进行安全诊断并生成测评整改建议",
    "operations": "ITIL事件：核心交换机故障导致业务中断，请分析根因并给出变更与SLA建议",
    "general": "数据库连接池耗尽导致接口超时，请给出合规的解决方案",
}

SCENARIO_LABELS = {
    "security": "等保/安全问题",
    "operations": "ITIL/运维事件",
    "general": "普通技术问题",
}

EXAMPLE_QUESTIONS = list(SCENARIO_QUESTIONS.values())


def detect_scenario_label(question: str) -> str:
    """Infer demo scenario from question keywords."""
    sup = Supervisor()
    lower = question.lower()
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


def run_forge(
    question: str,
    *,
    project_id: str = "cli-demo",
    protection_level: str = "3",
    initial_state: ProjectState | None = None,
) -> dict:
    """Execute the full Forge workflow from a fresh or resumed ProjectState."""
    load_dotenv()
    logger = get_logger("main")

    if initial_state is None:
        state = create_initial_state(project_id, current_phase="implementation")
        state["run_id"] = str(uuid4())[:8]
        state["messages"] = [HumanMessage(content=question)]
        state["rule_pack"] = {
            "pack_id": "system_integration_v1",
            "protection_level": protection_level,
        }
    else:
        state = prepare_state_for_run(
            initial_state,
            question,
            protection_level=protection_level,
        )

    logger.info(
        "Starting workflow | run_id=%s project=%s",
        state.get("run_id"),
        state.get("project_id"),
    )

    app = compile_workflow()
    return app.invoke(state)


def _priority_color(priority: str) -> str:
    p = priority.upper()
    if p == "P0":
        return red(priority)
    if p == "P1":
        return yellow(priority)
    return dim(priority)


def _get_recommended_solution(solution: dict) -> dict:
    rec_id = solution.get("recommended_solution_id", "")
    for sol in solution.get("solutions", []):
        if sol.get("id") == rec_id:
            return sol
    solutions = solution.get("solutions", [])
    return solutions[0] if solutions else {}


def print_pipeline_summary(result: dict) -> None:
    """Show planned vs executed pipeline stages."""
    plan = result.get("workflow_plan") or result.get("final_output", {}).get("workflow_plan") or {}
    trace = result.get("pipeline_trace") or result.get("final_output", {}).get("pipeline_trace") or []

    if not plan and not trace:
        return

    section("执行流水线 (Pipeline)")
    if plan.get("stages"):
        print(dim(f"  计划: {' → '.join(plan['stages'])}"))
        print(dim(f"  场景: {plan.get('scenario', 'N/A')} | 工作流: {plan.get('workflow', 'N/A')}"))
    if trace:
        print(dim("\n  实际执行:"))
        for entry in trace:
            status = entry.get("status", "?")
            agent = entry.get("agent", "?")
            icon = green("✓") if status == "success" else (red("✗") if status == "failed" else "…")
            err = f" — {entry.get('error', '')}" if status == "failed" else ""
            print(f"    {icon} {agent:<18} {status}{err}")


def print_agent_errors(result: dict) -> None:
    """Print recorded agent errors if any."""
    errors = result.get("agent_errors") or result.get("final_output", {}).get("agent_errors") or []
    if not errors:
        return
    section("执行异常 (Agent Errors)")
    for err in errors:
        print(red(f"  ✗ {err.get('agent', '?')}: {err.get('error', '')}"))


def print_security_result(result: dict) -> None:
    """Print SecurityAgent output."""
    final = result.get("final_output") or {}
    sec = final.get("security") or result.get("last_security_result") or {}
    if not sec:
        return

    section("等保安全分析 (SecurityAgent)")
    print(_wrap(sec.get("diagnosis", "")))
    print(
        dim(
            f"\n  保护级别: {sec.get('protection_level', 'N/A')}  |  "
            f"风险: {sec.get('risk_level', 'N/A')}"
        )
    )
    for r in sec.get("security_risks", [])[:6]:
        print(f"    • {r.get('title', '')} [{r.get('severity', '')}]")
    for c in sec.get("configuration_advice", [])[:5]:
        print(f"    → [{c.get('domain')}] {c.get('title')}")


def print_operations_result(result: dict) -> None:
    """Print OperationsAgent output."""
    final = result.get("final_output") or {}
    ops = final.get("operations") or result.get("last_operations_result") or {}
    if not ops:
        return

    section("ITIL 运维分析 (OperationsAgent)")
    print(_wrap(ops.get("situation_summary", "")))
    print(dim(f"\n  实践域: {ops.get('practice_area', 'N/A')}"))
    ig = ops.get("incident_guidance")
    if ig:
        print(dim(f"  事件优先级: {ig.get('priority', 'N/A')} | 影响: {ig.get('impact', '')}"))
        for step in ig.get("response_steps", [])[:5]:
            print(f"    → {step}")


def print_pm_advisor(result: dict) -> None:
    """Print PMAdvisorAgent summary."""
    final = result.get("final_output") or {}
    pm = final.get("pm_advice") or result.get("last_pm_advice") or {}
    if not pm:
        section("项目经理视角总结 (PMAdvisor)")
        print(yellow("  （未生成 PM 顾问报告）"))
        return

    section("项目经理视角总结 (PMAdvisor)")
    print(bold("\n  执行摘要"))
    print(_wrap(pm.get("summary", ""), indent=4))
    for a in pm.get("action_items", [])[:8]:
        pri = _priority_color(a.get("priority", "P2"))
        print(f"    [{pri}] {a.get('title', '')} — {a.get('owner', '待定')}")


def _agents_contributed(result: dict) -> list[str]:
    agents: list[str] = []
    if result.get("last_solution"):
        agents.append("ProblemSolver")
    if result.get("last_security_result"):
        agents.append("Security")
    if result.get("last_operations_result"):
        agents.append("Operations")
    if result.get("last_compliance_result"):
        agents.append("Compliance")
    if result.get("generated_documents"):
        agents.append("Document")
    if result.get("last_pm_advice"):
        agents.append("PMAdvisor")
    return agents


def print_result(result: dict, *, question: str = "") -> None:
    """Pretty-print the full Forge execution result."""
    final = result.get("final_output") or {}
    solution = final.get("solution") or result.get("last_solution") or {}
    compliance = final.get("compliance") or result.get("last_compliance_result") or {}
    docs = final.get("generated_documents") or result.get("generated_documents", [])
    retries = result.get("compliance_retry_count", 0)
    history = result.get("conversation_history", [])
    run_id = result.get("run_id") or final.get("run_id", "")

    if question:
        section("用户问题")
        print(_wrap(question))
    if run_id:
        print(dim(f"  运行 ID: {run_id}"))

    print_pipeline_summary(result)

    section("问题分析 (ProblemSolver)")
    if solution:
        print(_wrap(solution.get("problem_analysis", "无分析结果")))
        for c in solution.get("root_causes", []):
            print(f"    • {c}")
    else:
        print(yellow("  （无方案输出）"))

    section("推荐方案")
    if solution:
        rec = _get_recommended_solution(solution)
        print(f"  {green('★')} 方案 ID: {bold(solution.get('recommended_solution_id', 'N/A'))}")
        print(f"  标题: {bold(rec.get('title', 'N/A'))}")
        print(_wrap(rec.get("description", "")))
    else:
        print(yellow("  （无推荐方案）"))

    print_security_result(result)
    print_operations_result(result)

    section("合规检查结果 (Compliance)")
    comp_status = compliance.get("compliance_status", compliance.get("overall_status", "unknown"))
    risk = compliance.get("risk_level", "unknown")
    color = green if comp_status == "compliant" else (yellow if comp_status == "partial" else red)
    print(f"  状态: {color(comp_status)}  |  风险: {color(risk)}  |  重试: {retries}/2")

    section("生成资料 (DocumentAgent)")
    doc_gen = final.get("document_generation", "skipped" if not docs else "completed")
    if docs:
        print(green(f"  ✓ 已生成 {len(docs)} 份资料"))
        for i, doc in enumerate(docs, 1):
            print(f"  {cyan(f'[{i}]')} {bold(doc.get('title', ''))}")
    else:
        print(yellow(f"  资料生成: {doc_gen}"))

    if history:
        section("Agent 交互时间线")
        for entry in history[-15:]:
            ts = entry.get("timestamp", "")[:19]
            print(
                f"  {dim(ts)} {cyan(entry.get('agent', '?')):<16} "
                f"{entry.get('event', ''):<18} {entry.get('summary', '')}"
            )

    print_agent_errors(result)
    print_pm_advisor(result)

    print()
    print(bold("─" * 64))
    contributed = _agents_contributed(result)
    print(f"  {bold('完成')} | 合规={color(comp_status)} | 资料={len(docs)} 份 | 重试={retries} 次")
    if contributed:
        print(dim(f"  参与 Agent: {', '.join(contributed)}"))
    print(bold("─" * 64))
    print()


def print_documents_full(result: dict) -> None:
    docs = result.get("generated_documents") or result.get("final_output", {}).get(
        "generated_documents", []
    )
    for doc in docs:
        section(f"{doc.get('title')} [{doc.get('doc_type')}]")
        print(doc.get("content", ""))


def print_saved_state_summary(state: dict, metadata: dict) -> None:
    """Print a brief summary of a loaded state file."""
    section("已加载项目状态")
    print(f"  项目 ID: {state.get('project_id')}")
    print(f"  阶段: {state.get('current_phase')}")
    print(f"  保存时间: {metadata.get('saved_at', 'N/A')}")
    print(f"  上次问题: {metadata.get('last_question', 'N/A')}")
    print(f"  知识库条目: {len(state.get('knowledge_base', []))}")
    print(f"  对话记录: {len(state.get('conversation_history', []))}")
    if state.get("last_solution"):
        print(green("  ✓ 含 ProblemSolver 方案"))
    if state.get("last_pm_advice"):
        print(green("  ✓ 含 PMAdvisor 总结"))


def _prompt_question() -> str:
    print(dim("选择场景后将自动运行完整 Agent 流水线\n"))
    print(bold("场景:"))
    for key, label in SCENARIO_LABELS.items():
        q = SCENARIO_QUESTIONS[key]
        print(f"  {cyan(key)} — [{label}] {q[:40]}…")
    print(f"  {cyan('0')} — 自定义输入")
    print()
    choice = input("请输入场景 (security/operations/general) 或编号 1-3: ").strip().lower()
    key_map = {"1": "security", "2": "operations", "3": "general"}
    if choice in key_map:
        return SCENARIO_QUESTIONS[key_map[choice]]
    if choice in SCENARIO_QUESTIONS:
        return SCENARIO_QUESTIONS[choice]
    if choice == "0" or not choice:
        return input("\n请输入问题: ").strip()
    return choice


def _resolve_question(args: argparse.Namespace) -> str | None:
    if args.scenario:
        return SCENARIO_QUESTIONS[args.scenario]
    if args.example:
        return EXAMPLE_QUESTIONS[args.example - 1]
    if args.interactive:
        return _prompt_question()
    return args.question


def _resolve_state_path(args: argparse.Namespace) -> str | None:
    if args.load_state:
        return args.load_state
    if args.resume:
        return args.resume if args.resume != "auto" else str(default_state_path(args.project_id))
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Forge — 项目级 AI 操作系统命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(CLI_EPILOG),
    )
    parser.add_argument("question", nargs="?", help="问题描述（直接输入即运行完整流程）")
    parser.add_argument("-i", "--interactive", action="store_true", help="交互式选择场景/问题")
    parser.add_argument("--example", type=int, choices=[1, 2, 3], help="预设示例 1=等保 2=ITIL 3=通用")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIO_QUESTIONS),
        help="场景: security=等保 | operations=ITIL | general=通用技术",
    )
    parser.add_argument("--project-id", default="cli-demo", help="项目 ID")
    parser.add_argument("--protection-level", default="3", choices=["1", "2", "3", "4", "5"])
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    parser.add_argument("--show-docs", action="store_true", help="打印完整 Markdown 资料")
    parser.add_argument("--log-file", help="日志输出文件")
    parser.add_argument(
        "--save-state",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="运行后保存状态（默认 .forge_state/{project_id}.json）",
    )
    parser.add_argument(
        "--load-state",
        metavar="PATH",
        help="加载已保存状态；配合 --inspect 仅查看，不运行",
    )
    parser.add_argument(
        "--resume",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="从已保存状态恢复并运行新问题（默认路径同 --save-state）",
    )
    parser.add_argument("--inspect", action="store_true", help="仅查看 --load-state 内容，不执行流程")
    parser.add_argument("--list-states", action="store_true", help="列出 .forge_state/ 下已保存状态")
    parser.add_argument("--web", action="store_true", help="启动 FastAPI Web 服务")
    parser.add_argument(
        "--host",
        default=os.environ.get("FORGE_WEB_HOST", "127.0.0.1"),
        help="Web 服务监听地址（配合 --web）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FORGE_WEB_PORT", "8000")),
        help="Web 服务端口（配合 --web）",
    )
    args = parser.parse_args(argv)

    _configure_stdio()
    setup_logging("DEBUG" if args.verbose else "INFO", log_file=args.log_file)
    logger = get_logger("main")

    if args.web:
        try:
            import uvicorn
        except ImportError as exc:
            print(red("缺少依赖: pip install fastapi uvicorn"))
            return 1
        print(cyan(f"Forge Web → http://{args.host}:{args.port}/  (Ctrl+C 停止)"))
        uvicorn.run("web.app:app", host=args.host, port=args.port, log_level="info")
        return 0

    if args.list_states:
        banner()
        states = list_saved_states()
        if not states:
            print(yellow("  （暂无已保存状态，使用 --save-state 保存）"))
            return 0
        section("已保存项目状态")
        for s in states:
            print(f"  • {s.get('project_id')} — {s.get('saved_at', '?')}")
            print(dim(f"    {s.get('path')}"))
            if s.get("last_question"):
                print(dim(f"    问题: {s['last_question'][:60]}…"))
        return 0

    state_path = _resolve_state_path(args)
    loaded_state = None
    loaded_meta: dict = {}

    if state_path:
        try:
            loaded_state, loaded_meta = load_state_with_metadata(state_path)
            logger.info("Loaded state from %s", state_path)
        except FileNotFoundError:
            print(red(f"状态文件不存在: {state_path}"))
            return 1
        except Exception as exc:
            print(red(f"加载状态失败: {exc}"))
            return 1

    banner()

    if loaded_state and args.inspect:
        print_saved_state_summary(loaded_state, loaded_meta)
        return 0

    question = _resolve_question(args)
    if not question or not question.strip():
        if loaded_state and args.resume:
            print(yellow("恢复模式需要新问题，请提供 question 或 --scenario"))
            parser.print_help()
            return 1
        if not args.interactive:
            parser.print_help()
            return 0
        question = _prompt_question()

    if not question.strip():
        print(red("错误: 问题不能为空"))
        return 1

    scenario_label = detect_scenario_label(question)
    print(dim(f"项目 ID: {args.project_id} | 等保级别: {args.protection_level}"))
    print(dim(f"场景: {scenario_label}"))
    if loaded_state:
        print(dim(f"恢复自: {state_path}"))
    print(dim(f"问题: {question}"))
    print(dim("运行中… Supervisor 编排 → 多 Agent 协作流水线\n"))

    try:
        if loaded_state:
            # Merge project_id from CLI if resuming under same file
            if args.project_id != "cli-demo":
                loaded_state = dict(loaded_state)
                loaded_state["project_id"] = args.project_id
            result = run_forge(
                question,
                project_id=loaded_state.get("project_id", args.project_id),
                protection_level=args.protection_level,
                initial_state=loaded_state,
            )
        else:
            result = run_forge(
                question,
                project_id=args.project_id,
                protection_level=args.protection_level,
            )
    except KeyboardInterrupt:
        print(yellow("\n\n已取消"))
        return 130
    except Exception as exc:
        logger.exception("Workflow failed")
        print(red(f"\n✗ 执行失败: {exc}"))
        if args.verbose:
            traceback.print_exc()
        print(yellow("\n提示: 检查 .env 中的 DEEPSEEK_API_KEY，或使用 -v 查看详情"))
        return 1

    print_result(result, question=question)

    if args.show_docs and result.get("generated_documents"):
        print_documents_full(result)

    if args.save_state:
        out_path = default_state_path(args.project_id) if args.save_state == "auto" else args.save_state
        saved = save_state(
            result,
            out_path,
            metadata={"last_question": question, "scenario": scenario_label},
        )
        print(dim(f"\n状态已保存: {saved}"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
