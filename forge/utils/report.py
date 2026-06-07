"""Generate and save Markdown run reports from ProjectState."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forge.cli.stats import compute_run_stats


def generate_run_report(
    state: dict[str, Any],
    *,
    question: str = "",
    scenario: str = "",
    elapsed_ms: float = 0.0,
) -> str:
    """
    Build a Markdown run report from pipeline_trace and conversation_history.

    ``state`` is the post-run ProjectState dict (or run result).
    """
    run_id = state.get("run_id", "?")
    project_id = state.get("project_id", "?")
    solution = state.get("last_solution") or {}
    compliance = state.get("last_compliance_result") or {}
    docs = state.get("generated_documents") or []
    trace = state.get("pipeline_trace") or []
    history = state.get("conversation_history") or []
    errors = state.get("agent_errors") or []
    confidence = state.get("last_confidence_result") or {}
    stats = compute_run_stats(state, elapsed_ms=elapsed_ms or state.get("_elapsed_ms"))

    lines = [
        "# Forge 运行报告",
        "",
        "| 字段 | 值 |",
        "|------|-----|",
        f"| 项目 | {project_id} |",
        f"| Run ID | `{run_id}` |",
        f"| 场景 | {scenario or '—'} |",
        f"| 耗时 | {stats.get('elapsed_s', elapsed_ms / 1000 if elapsed_ms else '—')}s |",
        f"| 合规状态 | {stats.get('compliance_status', '—')} |",
        f"| 置信度 | {stats.get('confidence_score', '—')} |",
        f"| 生成时间 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} |",
        "",
        "## 问题输入",
        "",
        question or _question_from_history(history) or "（无）",
        "",
        "## 运行摘要",
        "",
        f"- Agent 调用: {stats.get('agents_success', 0)} 成功 / {stats.get('agents_failed', 0)} 失败",
        f"- 流水线步骤: {stats.get('pipeline_steps', 0)}",
        f"- 合规重试: {stats.get('compliance_retries', 0)}",
        f"- 资料生成: {stats.get('documents_generated', 0)} 份",
        f"- 风险等级: {stats.get('risk_level', '—')}",
        "",
        "## ProblemSolver 方案",
        "",
        f"- **类型**: {solution.get('problem_type', state.get('problem_type', '—'))}",
        f"- **推荐方案**: `{solution.get('recommended_solution_id', '—')}`",
        "",
        (solution.get("problem_analysis") or "（无分析）")[:800],
        "",
    ]

    refs = solution.get("rule_pack_references") or []
    if refs:
        lines.append("### Rule Pack 引用")
        for r in refs[:8]:
            lines.append(f"- `{r.get('rule_id', '?')}` {r.get('title', '')}")
        lines.append("")

    rationale = solution.get("decision_rationale")
    if rationale:
        lines.extend(["### 决策依据", "", rationale, ""])

    lines.extend(
        [
            "## Compliance 检查结果",
            "",
            f"- **状态**: {compliance.get('compliance_status', compliance.get('overall_status', '—'))}",
            f"- **模式**: {compliance.get('check_mode', '—')}",
            f"- **风险**: {compliance.get('risk_level', '—')}",
            "",
        ]
    )

    missing = compliance.get("missing_items") or []
    if missing:
        lines.append("### 合规缺口")
        for m in missing[:10]:
            lines.append(f"- {m}")
        lines.append("")

    explanations = compliance.get("check_explanations") or []
    if explanations:
        lines.append("### 合规检查追溯 (rule_id)")
        for e in explanations[:12]:
            lines.append(
                f"- `[{e.get('status', '?')}]` `{e.get('rule_id', '—')}` "
                f"({e.get('module', '?')}) {e.get('explanation', '')[:120]}"
            )
        lines.append("")

    retry_events = [h for h in history if h.get("event") in ("compliance_retry", "compliance_check")]
    if retry_events or int(state.get("compliance_retry_count") or 0) > 0:
        lines.extend(["## 合规重试过程", ""])
        lines.append(f"总重试次数: **{state.get('compliance_retry_count', 0)}**")
        lines.append("")
        for h in retry_events:
            d = h.get("detail") or {}
            lines.append(f"- `{h.get('agent')}` **{h.get('event')}**: {h.get('summary', '')}")
            if d:
                lines.append(f"  - detail: {d}")
        lines.append("")

    if docs:
        lines.extend(["## 生成资料", ""])
        for doc in docs:
            lines.append(f"- **[{doc.get('doc_type', '?')}]** {doc.get('title', '')}")
        lines.append("")

    pm = state.get("last_pm_advice") or {}
    if pm.get("summary") or pm.get("action_items"):
        lines.extend(["## PM 建议", "", (pm.get("summary") or "")[:600], ""])
        for a in (pm.get("action_items") or [])[:8]:
            lines.append(f"- [{a.get('priority', 'P2')}] {a.get('title', '')}")
        lines.append("")

    if confidence:
        lines.extend(
            [
                "## 置信度",
                f"- 分数: {confidence.get('score', state.get('confidence_score'))}",
                f"- 等级: {confidence.get('level', state.get('confidence_level'))}",
                f"- 建议: {confidence.get('recommendation', state.get('confidence_recommendation'))}",
                "",
            ]
        )

    tasks = state.get("execution_tasks") or []
    if tasks:
        lines.extend(["## 执行任务", f"共 {len(tasks)} 项:", ""])
        for t in tasks[:8]:
            lines.append(f"- [{t.get('status')}] {t.get('title', '')}")
        lines.append("")

    exec_results = state.get("execution_results") or []
    if exec_results:
        lines.extend(["## 执行结果（模拟）", ""])
        for r in exec_results[:8]:
            lines.append(f"- [{r.get('status')}] {r.get('task_id')}: {r.get('summary', '')}")
        lines.append("")

    key_decisions = _format_key_decisions(history, state)
    if key_decisions:
        lines.extend(["## 关键决策", "", key_decisions, ""])

    lines.extend(["## 流水线追踪 (pipeline_trace)", ""])
    if trace:
        lines.append("| Agent | 状态 | 耗时 | 输入摘要 | 输出摘要 |")
        lines.append("|-------|------|------|----------|----------|")
        for step in trace:
            agent = step.get("agent") or step.get("node") or "?"
            status = step.get("status", "?")
            dur = step.get("duration_ms")
            dur_s = f"{dur}ms" if dur is not None else "—"
            inp = (step.get("input_summary") or step.get("detail") or "")[:60].replace("|", "/")
            out = (step.get("output_summary") or "")[:60].replace("|", "/")
            lines.append(f"| {agent} | {status} | {dur_s} | {inp} | {out} |")
    else:
        lines.append("（无 pipeline_trace）")
    lines.append("")

    thinking = [h for h in history if h.get("event") == "thinking"]
    if thinking:
        lines.extend(["## 思考链路", ""])
        for h in thinking[-12:]:
            lines.append(f"- **{h.get('agent')}**: {h.get('summary', '')}")
        lines.append("")

    handoffs = [h for h in history if h.get("event") == "handoff"]
    if handoffs:
        lines.extend(["## Agent Handoff", ""])
        for h in handoffs:
            d = h.get("detail") or {}
            hs = d.get("handoff_summary") or {}
            extra = ""
            if hs.get("rule_ids"):
                extra = f" | rules: {', '.join(hs['rule_ids'][:4])}"
            lines.append(
                f"- {d.get('from_agent')} → **{d.get('to_agent')}** "
                f"({', '.join(d.get('payload_keys') or [])}){extra}"
            )
        lines.append("")

    if errors:
        lines.extend(["## 错误与降级", ""])
        for err in errors:
            lines.append(f"- **{err.get('agent')}**: {err.get('error', err)}")
        degraded = state.get("degraded_agents") or []
        if degraded:
            lines.append(f"- 降级 Agent: {', '.join(degraded)}")
        lines.append("")

    return "\n".join(lines)


def _format_key_decisions(history: list[dict[str, Any]], state: dict[str, Any]) -> str:
    """Summarize supervisor routes, thinking decisions, compliance retries, approval."""
    lines: list[str] = []
    for h in history:
        event = h.get("event", "")
        agent = h.get("agent", "?")
        summary = h.get("summary", "")
        detail = h.get("detail") or {}
        if event == "thinking":
            decision = detail.get("decision") or summary
            evidence = ", ".join(detail.get("evidence") or [])[:80]
            extra = f" | 证据: {evidence}" if evidence else ""
            lines.append(f"- **{agent}**（思考）: {decision}{extra}")
        elif event == "route":
            lines.append(
                f"- **Supervisor**（路由）: → {detail.get('next_agent', '?')} — {summary}"
            )
        elif event == "compliance_retry":
            lines.append(f"- **合规重试**: {summary}")
        elif event == "approval_decision":
            lines.append(
                f"- **审批门控**: {detail.get('approval_status', summary)} "
                f"(pending={detail.get('pending_count', 0)})"
            )
        elif event == "handoff":
            hs = detail.get("handoff_summary") or {}
            rule_part = ""
            if hs.get("rule_ids"):
                rule_part = f" | rules: {', '.join(hs['rule_ids'][:4])}"
            rat = (hs.get("decision_rationale") or "")[:100]
            rat_part = f" | {rat}" if rat else ""
            lines.append(
                f"- **Handoff**: {detail.get('from_agent')} → {detail.get('to_agent')}"
                f"{rule_part}{rat_part}"
            )
    conf = state.get("last_confidence_result") or {}
    if conf.get("recommendation"):
        lines.append(
            f"- **置信度结论**: {conf.get('score', state.get('confidence_score'))} "
            f"→ {conf.get('recommendation')} ({conf.get('level', '')})"
        )
    return "\n".join(lines[:20])


def _question_from_history(history: list[dict[str, Any]]) -> str:
    for h in history:
        if h.get("event") == "user_question":
            return str(h.get("summary") or "")
    return ""


def default_report_path(state: dict[str, Any]) -> Path:
    """Default path: ``reports/run_{run_id}.md``."""
    run_id = state.get("run_id") or "unknown"
    return Path("reports") / f"run_{run_id}.md"


def save_run_report(
    state: dict[str, Any],
    path: str | Path | None = None,
    *,
    question: str = "",
    scenario: str = "",
    elapsed_ms: float = 0.0,
) -> Path:
    """Write report Markdown to disk."""
    out = Path(path) if path else default_report_path(state)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        generate_run_report(
            state,
            question=question,
            scenario=scenario,
            elapsed_ms=elapsed_ms,
        ),
        encoding="utf-8",
    )
    return out


def prompt_save_run_report(
    state: dict[str, Any],
    *,
    question: str = "",
    scenario: str = "",
    elapsed_ms: float = 0.0,
    interactive: bool = True,
) -> Path | None:
    """Ask user (TTY) whether to save a run report; return path if saved."""
    if not interactive or not sys.stdin.isatty():
        return None
    try:
        raw = input("\n是否生成运行报告并保存到 reports/ 目录? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None
    if raw in ("n", "no", "否"):
        return None
    path = save_run_report(
        state,
        question=question,
        scenario=scenario,
        elapsed_ms=elapsed_ms,
    )
    return path
