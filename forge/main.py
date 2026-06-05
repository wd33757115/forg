"""Forge CLI — run the ProblemSolver ↔ Compliance closed-loop workflow."""

from __future__ import annotations

import argparse
import sys

from langchain_core.messages import HumanMessage

from forge.core import compile_workflow, create_initial_state
from forge.utils.env import load_dotenv


def run_forge(question: str, *, project_id: str = "cli-demo") -> dict:
    """Execute the full Forge workflow for a single user question."""
    load_dotenv()
    app = compile_workflow()
    state = create_initial_state(project_id, current_phase="implementation")
    state["messages"] = [HumanMessage(content=question)]
    return app.invoke(state)


def _print_result(result: dict) -> None:
    print("\n" + "=" * 60)
    print("FORGE 执行结果")
    print("=" * 60)

    if result.get("last_solution"):
        sol = result["last_solution"]
        print(f"\n[ProblemSolver] 推荐方案: {sol.get('recommended_solution_id')}")
        print(sol.get("problem_analysis", "")[:500])

    if result.get("last_compliance_result"):
        comp = result["last_compliance_result"]
        print(f"\n[Compliance] 状态: {comp.get('compliance_status')} | 风险: {comp.get('risk_level')}")
        print(f"重试次数: {result.get('compliance_retry_count', 0)}")
        for item in comp.get("missing_items", [])[:5]:
            print(f"  - {item}")

    print("\n--- 最终输出 ---")
    for msg in reversed(result.get("messages", [])):
        if getattr(msg, "name", None) == "forge_finalize":
            print(getattr(msg, "content", msg))
            break
    else:
        for msg in reversed(result.get("messages", [])):
            name = getattr(msg, "name", "")
            if name in ("problem_solver", "compliance", "supervisor"):
                print(f"[{name}]\n{getattr(msg, 'content', msg)[:1500]}")
                break


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forge — 项目级 AI 操作系统")
    parser.add_argument(
        "question",
        nargs="?",
        default="用户登录接口返回401，请诊断并给出合规的解决方案",
        help="要处理的问题描述",
    )
    parser.add_argument("--project-id", default="cli-demo", help="项目 ID")
    args = parser.parse_args(argv)

    print(f"问题: {args.question}")
    result = run_forge(args.question, project_id=args.project_id)
    _print_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
