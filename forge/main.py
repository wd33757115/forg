"""Forge CLI Demo — interactive command-line interface for the full agent pipeline."""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
import traceback
from typing import Any

from langchain_core.messages import HumanMessage

from forge.core import compile_workflow, create_initial_state
from forge.utils.env import load_dotenv
from forge.utils.logger import get_logger, setup_logging
from forge.utils.state_persistence import default_state_path, save_state

# ---------------------------------------------------------------------------
# Terminal styling (disabled when NO_COLOR is set)
# ---------------------------------------------------------------------------
_USE_COLOR = not os.environ.get("NO_COLOR")


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
    print(bold("║") + cyan("   Forge — 项目级 AI 操作系统 Demo") + bold("                        ║"))
    print(
        bold("║")
        + dim("   ProblemSolver → Compliance → Document → PMAdvisor")
        + bold("     ║")
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


def run_forge(question: str, *, project_id: str = "cli-demo", protection_level: str = "3") -> dict:
    """Execute the full Forge workflow."""
    load_dotenv()
    logger = get_logger("main")
    logger.info("Starting workflow | project=%s", project_id)

    app = compile_workflow()
    state = create_initial_state(project_id, current_phase="implementation")
    state["messages"] = [HumanMessage(content=question)]
    state["rule_pack"] = {
        "pack_id": "system_integration_v1",
        "protection_level": protection_level,
    }
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


def print_pm_advisor(result: dict) -> None:
    """Print project-manager advisory summary (highlighted final section)."""
    final = result.get("final_output") or {}
    pm = final.get("pm_advice") or result.get("last_pm_advice") or {}
    if not pm:
        section("项目经理视角总结 (PMAdvisor)")
        print(yellow("  （未生成 PM 顾问报告）"))
        return

    section("项目经理视角总结 (PMAdvisor)")
    print()
    print(bold("  执行摘要"))
    print(_wrap(pm.get("summary", ""), indent=4))

    overview = pm.get("situation_overview", "")
    if overview:
        print(bold("\n  现状概述"))
        print(_wrap(overview, indent=4))

    findings = pm.get("key_findings", [])
    if findings:
        print(bold("\n  关键发现"))
        for f in findings:
            print(f"    • {f}")

    risks = pm.get("risks", [])
    if risks:
        print(bold("\n  风险提示"))
        for r in risks:
            sev = r.get("severity", "medium")
            sev_col = red if sev in ("high", "critical") else yellow
            print(f"    • {bold(r.get('title', ''))} {sev_col(f'[{sev}]')}")
            if r.get("impact"):
                print(dim(f"      影响: {r['impact']}"))
            if r.get("mitigation"):
                print(dim(f"      缓解: {r['mitigation']}"))

    recs = pm.get("recommendations", [])
    if recs:
        print(bold("\n  决策建议"))
        for r in recs:
            print(f"    → {r}")

    actions = pm.get("action_items", [])
    if actions:
        print(bold("\n  行动项（按优先级）"))
        for a in actions:
            pri = _priority_color(a.get("priority", "P2"))
            owner = a.get("owner", "待定")
            hint = a.get("deadline_hint", "")
            print(f"    [{pri}] {a.get('title', '')} — {owner}" + (f" ({hint})" if hint else ""))

    decisions = pm.get("decision_points", [])
    if decisions:
        print(bold("\n  待决策事项"))
        for d in decisions:
            print(f"    ? {d}")

    outline = pm.get("report_outline", [])
    if outline:
        print(bold("\n  汇报材料大纲"))
        for line in outline:
            print(f"    {line}")

    notes = pm.get("stakeholder_notes", "")
    if notes:
        print(bold("\n  干系人沟通要点"))
        print(_wrap(notes, indent=4))


def print_result(result: dict, *, question: str = "") -> None:
    """Pretty-print the full Forge execution result."""
    final = result.get("final_output") or {}
    solution = final.get("solution") or result.get("last_solution") or {}
    compliance = final.get("compliance") or result.get("last_compliance_result") or {}
    docs = final.get("generated_documents") or result.get("generated_documents", [])
    retries = result.get("compliance_retry_count", 0)
    history = result.get("conversation_history", [])

    if question:
        section("用户问题")
        print(_wrap(question))

    # --- Problem analysis ---
    section("问题分析 (ProblemSolver)")
    if solution:
        print(_wrap(solution.get("problem_analysis", "无分析结果")))
        causes = solution.get("root_causes", [])
        if causes:
            print(dim("\n  根因:"))
            for c in causes:
                print(f"    • {c}")
    else:
        print(yellow("  （无方案输出）"))

    # --- Recommended solution ---
    section("推荐方案")
    if solution:
        rec = _get_recommended_solution(solution)
        status_icon = green("★") if rec else yellow("?")
        print(f"  {status_icon} 方案 ID: {bold(solution.get('recommended_solution_id', 'N/A'))}")
        print(f"  标题: {bold(rec.get('title', 'N/A'))}")
        print(_wrap(rec.get("description", "")))
        if rec.get("approach"):
            print(dim("\n  实施路径:"))
            print(_wrap(rec.get("approach", ""), indent=4))
        if rec.get("compliance_impact"):
            print(dim("\n  等保影响:"))
            print(_wrap(rec.get("compliance_impact", ""), indent=4))
        if rec.get("itil_guidance"):
            print(dim("\n  ITIL 指导:"))
            print(_wrap(rec.get("itil_guidance", ""), indent=4))
        actions = solution.get("next_actions", [])
        if actions:
            print(dim("\n  下一步:"))
            for a in actions:
                print(f"    → {a}")
    else:
        print(yellow("  （无推荐方案）"))

    # --- Compliance ---
    section("合规检查结果 (Compliance)")
    comp_status = compliance.get("compliance_status", compliance.get("overall_status", "unknown"))
    risk = compliance.get("risk_level", "unknown")
    color = green if comp_status == "compliant" else (yellow if comp_status == "partial" else red)
    print(f"  状态: {color(comp_status)}  |  风险: {color(risk)}  |  重试: {retries}/{2}")

    for mod in compliance.get("results", []):
        icon = green("✓") if mod.get("status") == "pass" else yellow("!")
        print(
            f"  {icon} {mod.get('module_name', mod.get('module'))}: "
            f"{mod.get('status')} (score {mod.get('score')})"
        )

    missing = compliance.get("missing_items", [])
    if missing:
        print(dim(f"\n  缺口 ({len(missing)} 项):"))
        for m in missing[:8]:
            print(f"    • {m}")
        if len(missing) > 8:
            print(dim(f"    … 另有 {len(missing) - 8} 项"))

    recs = compliance.get("recommendations", [])
    if recs:
        print(dim("\n  整改建议:"))
        for r in recs[:5]:
            print(f"    → {r}")

    # --- Documents ---
    section("生成资料 (DocumentAgent)")
    doc_gen = final.get("document_generation", "skipped" if not docs else "completed")
    if docs:
        print(green(f"  ✓ 已生成 {len(docs)} 份资料 ({doc_gen})"))
        print()
        for i, doc in enumerate(docs, 1):
            print(f"  {cyan(f'[{i}]')} {bold(doc.get('title', ''))}")
            print(dim(f"      类型: {doc.get('doc_type')}  |  ID: {doc.get('doc_id')}"))
            preview = doc.get("content", "").split("\n")[0][:80]
            print(dim(f"      {preview}…"))
        print(dim("\n  使用 --show-docs 查看完整资料内容"))
    else:
        print(yellow(f"  资料生成: {doc_gen}（合规未达 compliant/partial 或流程跳过）"))

    # --- Agent interaction timeline ---
    if history:
        section("Agent 交互时间线")
        for entry in history:
            ts = entry.get("timestamp", "")[:19]
            agent = entry.get("agent", "?")
            event = entry.get("event", "")
            summary = entry.get("summary", "")
            print(f"  {dim(ts)} {cyan(agent):<16} {event:<20} {summary}")

    # --- PM Advisor (final highlighted section) ---
    print_pm_advisor(result)

    # --- Footer ---
    print()
    print(bold("─" * 64))
    print(
        f"  {bold('完成')} | 合规={color(comp_status)} | "
        f"资料={len(docs)} 份 | 重试={retries} 次"
    )
    print(bold("─" * 64))
    print()


def print_documents_full(result: dict) -> None:
    """Print full document contents."""
    docs = result.get("generated_documents") or result.get("final_output", {}).get(
        "generated_documents", []
    )
    for doc in docs:
        section(f"{doc.get('title')} [{doc.get('doc_type')}]")
        print(doc.get("content", ""))


EXAMPLE_QUESTIONS = [
    "等保三级系统登录认证失败返回401，请诊断并生成整改资料",
    "ITIL事件：核心交换机故障导致业务中断，请分析根因并输出处理记录",
    "数据库连接池耗尽导致接口超时，请给出合规的解决方案",
]


def _prompt_question() -> str:
    print(dim("将运行完整流程: ProblemSolver → Compliance → Document → PMAdvisor\n"))
    print(bold("示例问题:"))
    for i, q in enumerate(EXAMPLE_QUESTIONS, 1):
        print(f"  {cyan(str(i))}. {q}")
    print(f"  {cyan('0')}. 自定义输入")
    print()
    choice = input("请选择 (1-3) 或直接输入问题: ").strip()
    if choice in ("1", "2", "3"):
        return EXAMPLE_QUESTIONS[int(choice) - 1]
    if choice == "0" or not choice:
        return input("\n请输入问题: ").strip()
    return choice


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Forge CLI Demo — 项目级 AI 操作系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            示例:
              py main.py "等保三级登录401故障，请诊断"
              py main.py -i
              py main.py --example 2
        """),
    )
    parser.add_argument("question", nargs="?", help="问题描述")
    parser.add_argument("-i", "--interactive", action="store_true", help="交互式选择问题")
    parser.add_argument("--example", type=int, choices=[1, 2, 3], help="使用预设示例问题")
    parser.add_argument("--project-id", default="cli-demo", help="项目 ID")
    parser.add_argument("--protection-level", default="3", choices=["1", "2", "3", "4", "5"])
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG 日志")
    parser.add_argument("--show-docs", action="store_true", help="打印完整资料内容")
    parser.add_argument("--log-file", help="日志输出文件")
    parser.add_argument(
        "--save-state",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="将 ProjectState 保存为 JSON（默认 .forge_state/{project_id}.json）",
    )
    args = parser.parse_args(argv)

    _configure_stdio()
    setup_logging("DEBUG" if args.verbose else "INFO", log_file=args.log_file)
    logger = get_logger("main")

    banner()

    if args.example:
        question = EXAMPLE_QUESTIONS[args.example - 1]
    elif args.interactive or not args.question:
        question = _prompt_question()
    else:
        question = args.question

    if not question.strip():
        print(red("错误: 问题不能为空"))
        return 1

    print(dim(f"项目 ID: {args.project_id} | 等保级别: {args.protection_level}"))
    print(dim(f"问题: {question}"))
    print(dim("运行中… (ProblemSolver → Compliance → Document → PMAdvisor)\n"))

    try:
        result = run_forge(
            question,
            project_id=args.project_id,
            protection_level=args.protection_level,
        )
    except KeyboardInterrupt:
        print(yellow("\n\n已取消"))
        return 130
    except Exception as exc:
        logger.error("Workflow failed: %s", exc)
        print(red(f"\n✗ 执行失败: {exc}"))
        if args.verbose:
            traceback.print_exc()
        print(yellow("\n提示: 检查 .env 中的 DEEPSEEK_API_KEY，或使用 -v 查看详情"))
        return 1

    print_result(result, question=question)

    if args.show_docs and result.get("generated_documents"):
        print_documents_full(result)

    if args.save_state:
        state_path = (
            default_state_path(args.project_id)
            if args.save_state == "auto"
            else args.save_state
        )
        saved = save_state(result, state_path)
        print(dim(f"\n状态已保存: {saved}"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
