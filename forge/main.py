"""Forge CLI — ProblemSolver → Compliance → Document full pipeline."""

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
    state["rule_pack"] = {"pack_id": "system_integration_v1", "protection_level": "3"}
    return app.invoke(state)


def _print_result(result: dict) -> None:
    print("\n" + "=" * 60)
    print("FORGE 完整执行结果")
    print("=" * 60)

    final = result.get("final_output") or {}

    if result.get("last_solution") or final.get("solution"):
        sol = final.get("solution") or result["last_solution"]
        print(f"\n[ProblemSolver] 推荐方案: {sol.get('recommended_solution_id')}")
        print(sol.get("problem_analysis", "")[:600])

    if result.get("last_compliance_result") or final.get("compliance"):
        comp = final.get("compliance") or result["last_compliance_result"]
        print(
            f"\n[Compliance] 状态: {comp.get('compliance_status')} | "
            f"风险: {comp.get('risk_level')} | 重试: {result.get('compliance_retry_count', 0)}"
        )
        for item in comp.get("missing_items", [])[:5]:
            print(f"  - {item}")

    docs = final.get("generated_documents") or result.get("generated_documents", [])
    if docs:
        print(f"\n[DocumentAgent] 已生成 {len(docs)} 份资料:")
        for doc in docs:
            print(f"\n--- [{doc.get('doc_type')}] {doc.get('title')} ---")
            print(doc.get("content", "")[:1200])
            if len(doc.get("content", "")) > 1200:
                print("…(内容已截断)")

    print("\n" + "=" * 60)
    print("最终汇总 (final_output)")
    print("=" * 60)
    if final:
        print(f"  合规状态: {final.get('compliance_status')}")
        print(f"  资料生成: {final.get('document_generation')} ({len(final.get('generated_documents', []))} 份)")
    else:
        for msg in reversed(result.get("messages", [])):
            if getattr(msg, "name", None) == "forge_finalize":
                print(getattr(msg, "content", msg)[:2000])
                break


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Forge — 项目级 AI 操作系统 (ProblemSolver → Compliance → Document)",
    )
    parser.add_argument(
        "question",
        nargs="?",
        default="等保三级系统登录认证失败，请诊断问题并生成整改资料",
        help="要处理的问题描述",
    )
    parser.add_argument("--project-id", default="cli-demo", help="项目 ID")
    args = parser.parse_args(argv)

    print(f"问题: {args.question}\n")
    result = run_forge(args.question, project_id=args.project_id)
    _print_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
