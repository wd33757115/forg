"""Rich-based CLI display for Forge (graceful fallback without rich)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    _RICH = True
except ImportError:
    _RICH = False


AGENT_DISPLAY = {
    "ProblemSolver": ("问题分析", "last_solution", "problem_analysis"),
    "Security": ("等保安全", "last_security_result", "diagnosis"),
    "Operations": ("ITIL运维", "last_operations_result", "situation_summary"),
    "Compliance": ("合规检查", "last_compliance_result", "compliance_status"),
    "Document": ("资料生成", "generated_documents", None),
    "PMAdvisor": ("PM总结", "last_pm_advice", "summary"),
}


class ForgeDisplay:
    """Terminal output for Forge CLI — uses Rich when available."""

    def __init__(self, *, use_color: bool = True) -> None:
        self._console = Console(force_terminal=use_color, highlight=False) if _RICH else None
        self.use_color = use_color and _RICH

    def banner(self) -> None:
        if self.use_color and self._console:
            self._console.print(
                Panel(
                    "[bold cyan]Forge[/] — 项目级 AI 操作系统\n"
                    "[dim]ProblemSolver → Security/Ops → Compliance → Document → PM[/]",
                    border_style="cyan",
                    box=box.ROUNDED,
                )
            )
            return
        print("\n=== Forge — 项目级 AI 操作系统 ===\n")

    def info(self, msg: str) -> None:
        if self.use_color and self._console:
            self._console.print(f"[dim]{msg}[/]")
        else:
            print(msg)

    def success(self, msg: str) -> None:
        if self.use_color and self._console:
            self._console.print(f"[green]{msg}[/]")
        else:
            print(msg)

    def warning(self, msg: str) -> None:
        if self.use_color and self._console:
            self._console.print(f"[yellow]{msg}[/]")
        else:
            print(msg)

    def error(self, msg: str) -> None:
        if self.use_color and self._console:
            self._console.print(f"[bold red]{msg}[/]")
        else:
            print(msg)

    def print_run_header(
        self,
        *,
        project_id: str,
        protection_level: str,
        scenario: str,
        question: str,
        llm_line: str,
        loaded_from: str | None = None,
    ) -> None:
        if self.use_color and self._console:
            meta = Table.grid(padding=(0, 2))
            meta.add_row("项目", project_id)
            meta.add_row("等保级别", protection_level)
            meta.add_row("场景", scenario)
            if loaded_from:
                meta.add_row("恢复自", loaded_from)
            meta.add_row("LLM", llm_line)
            self._console.print(Panel(meta, title="运行配置", border_style="blue"))
            self._console.print(Panel(question, title="用户问题", border_style="white"))
            return
        print(f"项目: {project_id} | 场景: {scenario}\n问题: {question}")

    def print_thinking_chain(self, history: list[dict[str, Any]], *, limit: int = 12) -> None:
        """Show agent thinking / decision chain."""
        thinking = [h for h in history if h.get("event") == "thinking"]
        if not thinking:
            return
        if self.use_color and self._console:
            table = Table(title="思考链路 (Thinking Chain)", box=box.SIMPLE_HEAD)
            table.add_column("时间", style="dim", max_width=19)
            table.add_column("Agent", style="cyan")
            table.add_column("思考 / 决策")
            for entry in thinking[-limit:]:
                ts = entry.get("timestamp", "")[:19]
                agent = entry.get("agent", "?")
                summary = entry.get("summary", "")
                decision = (entry.get("detail") or {}).get("decision")
                text = summary + (f"\n[dim]→ {decision}[/]" if decision else "")
                table.add_row(ts, agent, text)
            self._console.print(table)
            return
        print("\n--- 思考链路 ---")
        for entry in thinking[-limit:]:
            print(f"  [{entry.get('agent')}] {entry.get('summary')}")

    def print_agent_contributions(self, result: dict[str, Any]) -> None:
        trace = result.get("pipeline_trace") or []
        status_map = {e.get("agent"): e.get("status") for e in trace}
        if self.use_color and self._console:
            table = Table(title="Agent 贡献摘要", box=box.ROUNDED)
            table.add_column("Agent", style="bold")
            table.add_column("领域")
            table.add_column("状态")
            table.add_column("产出摘要")
            for agent_name, (label, state_key, preview_field) in AGENT_DISPLAY.items():
                trace_key = agent_name.lower()
                if agent_name == "ProblemSolver":
                    trace_key = "problem_solver"
                elif agent_name == "PMAdvisor":
                    trace_key = "pm_advisor"
                status = status_map.get(trace_key, "—")
                st_style = {"success": "green", "failed": "red"}.get(status, "dim")
                payload = result.get(state_key)
                if state_key == "generated_documents":
                    preview = f"{len(payload or [])} 份资料"
                elif payload and preview_field and isinstance(payload, dict):
                    val = str(payload.get(preview_field, ""))[:60]
                    preview = val + ("…" if len(val) >= 60 else "")
                elif payload:
                    preview = "已产出"
                else:
                    preview = "—"
                table.add_row(agent_name, label, Text(status, style=st_style), preview)
            self._console.print(table)
            return

    def print_summary_footer(self, result: dict[str, Any], *, elapsed_ms: float | None) -> None:
        final = result.get("final_output") or {}
        compliance = final.get("compliance") or result.get("last_compliance_result") or {}
        docs = result.get("generated_documents") or []
        comp_status = compliance.get("compliance_status", "unknown")
        retries = result.get("compliance_retry_count", 0)
        problem_type = result.get("problem_type") or (result.get("last_solution") or {}).get("problem_type", "—")
        timing = f"{elapsed_ms / 1000:.1f}s" if elapsed_ms else "—"
        errors = len(result.get("agent_errors") or [])

        if self.use_color and self._console:
            grid = Table.grid(padding=(0, 2))
            grid.add_row("问题类型", str(problem_type))
            grid.add_row("合规状态", comp_status)
            grid.add_row("资料", f"{len(docs)} 份")
            grid.add_row("重试", str(retries))
            grid.add_row("耗时", timing)
            if errors:
                grid.add_row("异常", f"{errors} 个 Agent")
            self._console.print(Panel(grid, title="运行摘要", border_style="green"))
            return
        print(f"\n完成 | 类型={problem_type} | 合规={comp_status} | 耗时={timing}")

    def print_errors(self, result: dict[str, Any]) -> None:
        errors = result.get("agent_errors") or []
        degraded = result.get("degraded_agents") or []
        if not errors and not degraded:
            return
        if self.use_color and self._console:
            lines = []
            for err in errors:
                lines.append(f"[red]✗ {err.get('agent')}: {err.get('error')}[/]")
            if degraded:
                lines.append(f"[yellow]降级: {', '.join(degraded)}[/]")
            self._console.print(Panel("\n".join(lines), title="异常与降级", border_style="red"))


def collect_user_feedback(
    result: dict[str, Any],
    *,
    question: str,
    interactive: bool = True,
) -> dict[str, Any] | None:
    """
    Prompt for 1-5 satisfaction score after a run (TTY only).

    Returns a knowledge_base entry dict, or None if skipped.
    """
    if not interactive or not sys.stdin.isatty():
        return None
    try:
        print()
        raw = input("请为本次方案满意度打分 (1-5，回车跳过): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not raw:
        return None
    try:
        score = int(raw)
    except ValueError:
        return None
    if score < 1 or score > 5:
        return None

    run_id = result.get("run_id", "unknown")
    solution = result.get("last_solution") or {}
    return {
        "id": f"kb-feedback-{run_id}-{score}",
        "category": "user_feedback",
        "content": f"用户对 run {run_id} 满意度 {score}/5",
        "source": "cli",
        "tags": ["feedback", f"score_{score}", result.get("problem_type", "unknown")],
        "metadata": {
            "score": score,
            "run_id": run_id,
            "question": question[:500],
            "recommended_solution_id": solution.get("recommended_solution_id"),
            "compliance_status": (result.get("last_compliance_result") or {}).get("compliance_status"),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    }
