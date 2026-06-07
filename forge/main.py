"""Forge CLI — command-line interface for the multi-agent project pipeline."""

from __future__ import annotations

import os
import sys
import time
import traceback

from forge.cli.ansi import red, section, yellow
from forge.cli.demo_display import ForgeDemoDisplay
from forge.cli.display import collect_user_feedback
from forge.cli.parser import build_cli_parser
from forge.cli.resolvers import (
    TYPE_LABELS,
    detect_scenario_label,
    llm_status_line,
    resolve_question,
    resolve_state_path,
    resolve_type_hint,
)
from forge.cli.result_print import (
    print_documents_full,
    print_result,
    print_saved_state_summary,
)
from forge.cli.runner import run_forge
from forge.cli.scenarios import SCENARIO_QUESTIONS  # noqa: F401 — web backward compat
from forge.config import get_settings
from forge.utils.env import load_dotenv
from forge.utils.llm import get_api_key
from forge.utils.logger import get_logger, setup_logging
from forge.utils.result_serializer import default_run_result_path, save_run_result
from forge.utils.report import prompt_save_run_report
from forge.utils.run_report import default_report_path as legacy_report_path
from forge.utils.run_report import write_run_report
from forge.utils.state_persistence import list_saved_states, load_state_with_metadata, save_state

__all__ = [
    "SCENARIO_QUESTIONS",
    "detect_scenario_label",
    "main",
    "run_forge",
]


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


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    if raw_argv and raw_argv[0] == "kb":
        from forge.cli.kb import kb_main

        return kb_main(raw_argv[1:])

    parser = build_cli_parser()
    args = parser.parse_args(raw_argv)

    _configure_stdio()
    load_dotenv()
    settings = get_settings()
    log_level = "DEBUG" if args.verbose else settings.log_level
    setup_logging(log_level, log_file=args.log_file)
    logger = get_logger("main")
    use_color = not os.environ.get("NO_COLOR")
    display = ForgeDemoDisplay(use_color=use_color and not args.plain)

    if args.web:
        try:
            import uvicorn
        except ImportError:
            print(red("缺少依赖: pip install fastapi uvicorn"))
            return 1
        from forge.cli.ansi import cyan

        print(cyan(f"Forge Web → http://{args.host}:{args.port}/  (Ctrl+C 停止)"))
        uvicorn.run("web.app:app", host=args.host, port=args.port, log_level="info")
        return 0

    if args.list_states:
        display.banner()
        states = list_saved_states()
        if not states:
            print(yellow("  （暂无已保存状态，使用 --save-state 保存）"))
            return 0
        section("已保存项目状态")
        for s in states:
            print(f"  • {s.get('project_id')} — {s.get('saved_at', '?')}")
            from forge.cli.ansi import dim

            print(dim(f"    {s.get('path')}"))
            if s.get("last_question"):
                print(dim(f"    问题: {s['last_question'][:60]}…"))
        return 0

    state_path = resolve_state_path(args)
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

    display.banner()

    if loaded_state and args.inspect:
        print_saved_state_summary(loaded_state, loaded_meta)
        return 0

    question = resolve_question(args)
    if not question or not question.strip():
        if loaded_state and args.resume:
            print(yellow("恢复模式需要新问题，请提供 question 或 --scenario"))
            parser.print_help()
            return 1
        if not args.interactive:
            parser.print_help()
            return 0
        from forge.cli.resolvers import prompt_question

        question = prompt_question()

    if not question.strip():
        print(red("错误: 问题不能为空"))
        return 1

    type_hint = resolve_type_hint(args)
    scenario_label = TYPE_LABELS.get(args.type, "") if args.type else detect_scenario_label(question)
    if not scenario_label:
        scenario_label = detect_scenario_label(question)
    display.print_run_header(
        project_id=args.project_id,
        protection_level=args.protection_level,
        scenario=scenario_label,
        question=question,
        llm_line=llm_status_line(),
        loaded_from=str(state_path) if loaded_state else None,
    )
    display.info("运行中… Supervisor 编排 → 多 Agent 协作流水线\n")

    if args.approve and args.reject:
        print(red("错误: --approve 与 --reject 不能同时使用"))
        return 1
    force_approval = "approve" if args.approve else ("reject" if args.reject else None)

    started = time.perf_counter()
    problem_hint = type_hint or (args.scenario if args.scenario in ("security", "itil", "mixed", "general") else None)
    use_demo_seed = args.demo_seed or (
        not args.no_demo_seed and bool(args.type or args.scenario) and not loaded_state
    )
    try:
        if loaded_state:
            if args.project_id != "cli-demo":
                loaded_state = dict(loaded_state)
                loaded_state["project_id"] = args.project_id
            result = run_forge(
                question,
                project_id=loaded_state.get("project_id", args.project_id),
                protection_level=args.protection_level,
                problem_type_hint=problem_hint,
                check_mode=args.check_mode,
                demo_seed=use_demo_seed,
                auto_approve=args.auto_approve,
                force_approval=force_approval,
                execution_mode=args.execution_mode,
                initial_state=loaded_state,
            )
        else:
            result = run_forge(
                question,
                project_id=args.project_id,
                protection_level=args.protection_level,
                problem_type_hint=problem_hint,
                check_mode=args.check_mode,
                demo_seed=use_demo_seed,
                auto_approve=args.auto_approve,
                force_approval=force_approval,
                execution_mode=args.execution_mode,
            )
        result["_elapsed_ms"] = (time.perf_counter() - started) * 1000
    except KeyboardInterrupt:
        print(yellow("\n\n已取消"))
        return 130
    except Exception as exc:
        logger.exception("Workflow failed")
        print(red(f"\n✗ 执行失败: {exc}"))
        if args.verbose:
            traceback.print_exc()
        key_hint = "已配置" if get_api_key() else "未配置"
        print(yellow(f"\n提示: LLM API Key {key_hint}，检查 .env 中 FORGE_LLM_PROVIDER / DEEPSEEK_API_KEY"))
        print(yellow("      使用 -v 查看完整堆栈"))
        return 1

    elapsed_ms = result.get("_elapsed_ms", 0)
    display.info(f"总耗时: {elapsed_ms / 1000:.2f}s")

    if args.plain:
        print_result(result, question=question)
        display.print_thinking_chain(result.get("conversation_history") or [])
        display.print_agent_contributions(result)
        display.print_errors(result)
        display.print_summary_footer(result, elapsed_ms=elapsed_ms)
    else:
        display.print_demo_result(result, question=question, elapsed_ms=elapsed_ms)

    if args.report:
        report_path = (
            legacy_report_path(args.project_id, result.get("run_id") or "unknown")
            if args.report == "auto"
            else args.report
        )
        written = write_run_report(
            result,
            report_path,
            question=question,
            scenario=scenario_label,
            elapsed_ms=elapsed_ms,
        )
        display.info(f"运行报告: {written}")
    elif not args.no_report_prompt:
        saved_report = prompt_save_run_report(
            result,
            question=question,
            scenario=scenario_label,
            elapsed_ms=elapsed_ms,
        )
        if saved_report:
            display.success(f"运行报告已保存: {saved_report}")

    if not args.no_feedback:
        feedback_entry = collect_user_feedback(result, question=question)
        if feedback_entry:
            result["knowledge_base"] = list(result.get("knowledge_base", [])) + [feedback_entry]
            display.success(f"感谢反馈！评分 {feedback_entry['metadata']['score']}/5 已记入知识库")

    if args.show_docs and result.get("generated_documents"):
        print_documents_full(result)

    do_save_state = args.save_state or args.save
    if do_save_state:
        from forge.utils.state_persistence import default_state_path

        out_path = (
            default_state_path(args.project_id)
            if do_save_state == "auto"
            else do_save_state
        )
        saved = save_state(
            result,
            out_path,
            metadata={"last_question": question, "scenario": scenario_label},
        )
        display.info(f"状态已保存: {saved}")

    do_save_result = args.save_result or args.save
    if do_save_result:
        run_id = result.get("run_id") or "unknown"
        if do_save_result == "auto":
            out_json = default_run_result_path(run_id, args.project_id)
        else:
            out_json = do_save_result
        saved_json = save_run_result(
            result,
            out_json,
            question=question,
            scenario=scenario_label,
            elapsed_ms=elapsed_ms,
        )
        display.info(f"运行结果 JSON: {saved_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
