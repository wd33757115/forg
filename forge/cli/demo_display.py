"""Rich CLI demo — full pipeline storyboard for Forge (v1.1)."""

from __future__ import annotations

from typing import Any

from forge.cli.display import ForgeDisplay, _RICH
from forge.cli.stats import compute_run_stats

if _RICH:
    from rich import box
    from rich.columns import Columns
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.tree import Tree


_STATUS_STYLE = {
    "compliant": "bold green",
    "partial": "bold yellow",
    "non_compliant": "bold red",
    "pass": "green",
    "gaps_found": "yellow",
    "critical": "red",
    "success": "green",
    "failed": "red",
    "skipped": "dim",
}


class ForgeDemoDisplay(ForgeDisplay):
    """
    Enhanced demo renderer: 问题 → 方案 → 合规(含重试) → 资料 → PM → 思考链路 → 统计.
    """

    def print_demo_result(
        self,
        result: dict[str, Any],
        *,
        question: str = "",
        elapsed_ms: float | None = None,
    ) -> None:
        """Primary post-run demo output (Rich when available)."""
        if not self.use_color or not self._console:
            self._print_demo_plain(result, question=question, elapsed_ms=elapsed_ms)
            return

        stats = compute_run_stats(result, elapsed_ms=elapsed_ms)
        self._console.print()
        self._print_pipeline_banner(result)
        if question:
            self._console.print(Panel(question, title="① 用户问题", border_style="white"))
        self._print_solution_panel(result)
        self._print_compliance_panel(result, stats)
        self._print_compliance_retry_timeline(result)
        self._print_documents_panel(result)
        self._print_pm_panel(result)
        self._print_thinking_chain_rich(result)
        self._print_handoff_chain(result)
        self.print_agent_contributions(result)
        self.print_errors(result)
        self._print_stats_panel(stats)
        self._console.print()

    def _status_text(self, value: str) -> Text:
        style = _STATUS_STYLE.get(str(value).lower(), "")
        return Text(str(value), style=style) if style else Text(str(value))

    def _print_pipeline_banner(self, result: dict[str, Any]) -> None:
        plan = result.get("workflow_plan") or {}
        stages = plan.get("stages") or [
            "ProblemSolver",
            "Specialists",
            "Compliance",
            "Document",
            "PMAdvisor",
        ]
        flow = " → ".join(stages)
        trace = result.get("pipeline_trace") or []
        self._console.print(
            Panel(
                f"[cyan]{flow}[/]\n[dim]已执行 {len(trace)} 步 | run_id={result.get('run_id', '—')}[/]",
                title="Forge 流水线",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )

    def _print_solution_panel(self, result: dict[str, Any]) -> None:
        solution = result.get("last_solution") or {}
        if not solution:
            self._console.print(Panel("[dim]无方案输出[/]", title="② ProblemSolver 方案", border_style="blue"))
            return

        ptype = solution.get("problem_type", result.get("problem_type", "—"))
        analysis = (solution.get("problem_analysis") or "")[:600]
        rec_id = solution.get("recommended_solution_id", "—")
        refs = solution.get("rule_pack_references") or []

        body = Table.grid(padding=(0, 1))
        body.add_row("问题类型", str(ptype))
        body.add_row("推荐方案", f"[bold]{rec_id}[/]")
        body.add_row("分析摘要", analysis + ("…" if len(solution.get("problem_analysis", "")) > 600 else ""))

        if refs:
            ref_lines = "\n".join(
                f"• [dim]{r.get('rule_id')}[/] {r.get('title', '')}" for r in refs[:5]
            )
            body.add_row("Rule Pack", ref_lines)

        causes = solution.get("root_causes") or []
        if causes:
            body.add_row("根因", "\n".join(f"• {c}" for c in causes[:4]))

        self._console.print(Panel(body, title="② ProblemSolver 方案", border_style="blue"))

    def _print_compliance_panel(self, result: dict[str, Any], stats: dict[str, Any]) -> None:
        compliance = result.get("last_compliance_result") or {}
        if not compliance:
            return

        status = compliance.get("compliance_status", compliance.get("overall_status", "unknown"))
        mode = compliance.get("check_mode", "advisory")
        retries = stats.get("compliance_retries", 0)

        grid = Table.grid(padding=(0, 2))
        grid.add_row("合规状态", self._status_text(status))
        grid.add_row("风险等级", self._status_text(compliance.get("risk_level", "—")))
        grid.add_row("检查模式", mode)
        grid.add_row("重试次数", f"{retries} / 2")

        items_table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
        items_table.add_column("模块", style="cyan")
        items_table.add_column("得分")
        items_table.add_column("状态")
        items_table.add_column("摘要", max_width=40)
        for mod in compliance.get("results", [])[:3]:
            items_table.add_row(
                mod.get("module", "?"),
                str(mod.get("score", "—")),
                self._status_text(mod.get("status", "—")),
                (mod.get("summary") or "")[:40],
            )

        content = Table.grid()
        content.add_row(grid)
        content.add_row(items_table)

        missing = compliance.get("missing_items") or []
        if missing:
            miss = "\n".join(f"[yellow]•[/] {m[:80]}" for m in missing[:5])
            if len(missing) > 5:
                miss += f"\n[dim]… 另有 {len(missing) - 5} 项[/]"
            content.add_row(Panel(miss, title="缺口", border_style="yellow"))

        self._console.print(Panel(content, title="③ Compliance 合规检查", border_style="magenta"))

    def _print_compliance_retry_timeline(self, result: dict[str, Any]) -> None:
        history = result.get("conversation_history") or []
        retry_related = [
            h
            for h in history
            if h.get("event")
            in ("compliance_retry", "compliance_check", "solution_generated", "handoff")
        ]
        if not retry_related:
            return

        tree = Tree("[bold]合规闭环时间线[/]")
        for entry in retry_related[-12:]:
            event = entry.get("event", "?")
            agent = entry.get("agent", "?")
            summary = entry.get("summary", "")
            detail = entry.get("detail") or {}
            label = f"[cyan]{agent}[/] [{event}] {summary}"
            branch = tree.add(label)
            if event == "compliance_retry":
                branch.add(
                    f"重试 #{detail.get('retry_count')} | "
                    f"状态={detail.get('compliance_status')} | "
                    f"缺口={detail.get('missing_count')}"
                )
            elif event == "compliance_check":
                branch.add(
                    f"结果={detail.get('compliance_status')} | "
                    f"风险={detail.get('risk_level')}"
                )
            elif event == "handoff":
                branch.add(
                    f"{detail.get('from_agent')} → {detail.get('to_agent')} "
                    f"keys={detail.get('payload_keys', [])}"
                )

        self._console.print(Panel(tree, border_style="yellow", title="合规重试 & Handoff"))

    def _print_documents_panel(self, result: dict[str, Any]) -> None:
        docs = result.get("generated_documents") or []
        if not docs:
            skipped = (result.get("final_output") or {}).get("document_generation", "skipped")
            self._console.print(
                Panel(f"[dim]资料生成: {skipped}[/]", title="④ Document 资料", border_style="dim")
            )
            return

        table = Table(box=box.SIMPLE_HEAD)
        table.add_column("#", style="dim")
        table.add_column("类型")
        table.add_column("标题")
        for i, doc in enumerate(docs, 1):
            table.add_row(str(i), doc.get("doc_type", ""), doc.get("title", ""))
        self._console.print(
            Panel(table, title=f"④ Document 资料（{len(docs)} 份）", border_style="green")
        )

    def _print_pm_panel(self, result: dict[str, Any]) -> None:
        pm = result.get("last_pm_advice") or {}
        if not pm:
            return
        summary = (pm.get("summary") or "")[:500]
        actions = pm.get("action_items") or []
        body = summary
        if actions:
            body += "\n\n[bold]行动项[/]\n" + "\n".join(
                f"• [{a.get('priority', 'P2')}] {a.get('title', '')}" for a in actions[:5]
            )
        self._console.print(Panel(body, title="⑤ PM 顾问建议", border_style="bright_blue"))

    def _print_thinking_chain_rich(self, result: dict[str, Any]) -> None:
        thinking = [h for h in (result.get("conversation_history") or []) if h.get("event") == "thinking"]
        if not thinking:
            return
        table = Table(title="思考链路 (Thinking Chain)", box=box.SIMPLE_HEAD, show_lines=True)
        table.add_column("Agent", style="cyan", width=16)
        table.add_column("思考")
        table.add_column("决策 / 证据", style="dim")
        for entry in thinking[-10:]:
            detail = entry.get("detail") or {}
            decision = detail.get("decision", "")
            evidence = ", ".join(detail.get("evidence") or [])[:60]
            extra = decision or evidence
            table.add_row(entry.get("agent", "?"), entry.get("summary", ""), extra)
        self._console.print(table)

    def _print_handoff_chain(self, result: dict[str, Any]) -> None:
        handoffs = [h for h in (result.get("conversation_history") or []) if h.get("event") == "handoff"]
        if not handoffs:
            return
        lines = []
        for h in handoffs[-6:]:
            d = h.get("detail") or {}
            lines.append(
                f"• {d.get('from_agent')} → [bold]{d.get('to_agent')}[/] "
                f"({', '.join(d.get('payload_keys') or [])})"
            )
        self._console.print(Panel("\n".join(lines), title="Agent Handoff", border_style="dim"))

    def _print_stats_panel(self, stats: dict[str, Any]) -> None:
        grid = Table.grid(padding=(0, 2))
        grid.add_row("耗时", f"{stats.get('elapsed_s', '—')}s")
        grid.add_row("流水线步骤", str(stats.get("pipeline_steps", 0)))
        grid.add_row("Agent 调用", f"{stats.get('agents_success', 0)} 成功 / {stats.get('agents_failed', 0)} 失败")
        grid.add_row("思考步骤", str(stats.get("thinking_steps", 0)))
        grid.add_row("合规重试", str(stats.get("compliance_retries", 0)))
        grid.add_row("Handoff", str(stats.get("handoffs", 0)))
        grid.add_row("问题类型", str(stats.get("problem_type", "—")))
        grid.add_row("置信度", f"{stats.get('confidence_score', 0):.0%}")
        grid.add_row("风险", str(stats.get("risk_level", "—")))
        self._console.print(Panel(grid, title="运行统计", border_style="green", box=box.ROUNDED))

    def _print_demo_plain(
        self,
        result: dict[str, Any],
        *,
        question: str,
        elapsed_ms: float | None,
    ) -> None:
        """Fallback when Rich is unavailable."""
        from forge.cli.result_print import print_result

        print_result(result, question=question)
        self.print_thinking_chain(result.get("conversation_history") or [])
        self.print_agent_contributions(result)
        stats = compute_run_stats(result, elapsed_ms=elapsed_ms)
        print(f"\n--- 统计: 耗时={stats.get('elapsed_s')}s | 重试={stats.get('compliance_retries')} ---")
