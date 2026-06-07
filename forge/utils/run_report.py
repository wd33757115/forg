"""Generate Markdown run reports from pipeline_trace and artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_run_report_markdown(
    result: dict[str, Any],
    *,
    question: str = "",
    scenario: str = "",
    elapsed_ms: float = 0.0,
) -> str:
    """Build a human-readable Markdown summary of a Forge run."""
    run_id = result.get("run_id", "?")
    project_id = result.get("project_id", "?")
    solution = result.get("last_solution") or {}
    compliance = result.get("last_compliance_result") or {}
    docs = result.get("generated_documents") or []
    trace = result.get("pipeline_trace") or []
    errors = result.get("agent_errors") or []
    confidence = result.get("last_confidence_result") or {}
    tasks = result.get("execution_tasks") or []

    lines = [
        f"# Forge 运行报告",
        "",
        f"| 字段 | 值 |",
        f"|------|-----|",
        f"| 项目 | {project_id} |",
        f"| Run ID | {run_id} |",
        f"| 场景 | {scenario or '—'} |",
        f"| 耗时 | {elapsed_ms / 1000:.2f}s |",
        f"| 生成时间 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} |",
        "",
        "## 问题",
        question or "（无）",
        "",
        "## 方案摘要",
        f"- 类型: {solution.get('problem_type', result.get('problem_type', '—'))}",
        f"- 推荐方案: {solution.get('recommended_solution_id', '—')}",
        f"- 分析: {(solution.get('problem_analysis') or '—')[:300]}",
        "",
        "## 合规",
        f"- 状态: {compliance.get('compliance_status', '—')}",
        f"- 模式: {compliance.get('check_mode', '—')}",
        f"- 风险: {compliance.get('risk_level', '—')}",
        f"- 缺口数: {len(compliance.get('missing_items', []))}",
        "",
    ]

    if confidence:
        lines.extend(
            [
                "## 置信度",
                f"- 分数: {confidence.get('score', result.get('confidence_score', '—'))}",
                f"- 等级: {confidence.get('level', result.get('confidence_level', '—'))}",
                f"- 建议: {confidence.get('recommendation', result.get('confidence_recommendation', '—'))}",
                "",
            ]
        )
        factors = confidence.get("factors") or {}
        if factors:
            lines.append(
                f"- 因子: 合规={factors.get('compliance_factor')} "
                f"证据={factors.get('evidence_factor')} "
                f"历史={factors.get('history_factor')}"
            )
            lines.append("")

    if tasks:
        lines.extend(["## 执行任务", f"共 {len(tasks)} 项:"])
        for t in tasks[:8]:
            lines.append(f"- [{t.get('status')}] {t.get('title', '')}")
        lines.append("")

    lines.extend(
        [
            "## 资料",
            f"共 {len(docs)} 份: "
            + ", ".join(d.get("doc_type", "?") for d in docs[:10])
            if docs
            else "无",
            "",
            "## 流水线追踪",
        ]
    )

    if trace:
        for step in trace:
            status = step.get("status", "?")
            agent = step.get("agent", "?")
            detail = step.get("detail", "")
            dur = step.get("duration_ms")
            dur_s = f" {dur}ms" if dur is not None else ""
            mode = step.get("check_mode")
            mode_s = f" mode={mode}" if mode else ""
            lines.append(f"- **{agent}** [{status}]{dur_s}{mode_s} {detail}")
    else:
        lines.append("- （无 pipeline_trace）")

    handoffs = [h for h in (result.get("conversation_history") or []) if h.get("event") == "handoff"]
    if handoffs:
        lines.extend(["", "## Agent Handoff"])
        for h in handoffs:
            d = h.get("detail") or {}
            lines.append(
                f"- {d.get('from_agent')} → {d.get('to_agent')} "
                f"({', '.join(d.get('payload_keys') or [])})"
            )

    if errors:
        lines.extend(["", "## 错误"])
        for err in errors:
            lines.append(f"- {err.get('agent')}: {err.get('error', err)}")

    pm = result.get("last_pm_advice") or {}
    if pm.get("summary"):
        lines.extend(["", "## PM 摘要", pm["summary"][:500]])

    pending = result.get("pending_approvals") or []
    if pending:
        lines.extend(["", "## 待审批", f"共 {len(pending)} 项待人工审批"])

    return "\n".join(lines)


def write_run_report(
    result: dict[str, Any],
    path: str | Path,
    *,
    question: str = "",
    scenario: str = "",
    elapsed_ms: float = 0.0,
) -> Path:
    """Write Markdown report to disk and return the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        build_run_report_markdown(
            result,
            question=question,
            scenario=scenario,
            elapsed_ms=elapsed_ms,
        ),
        encoding="utf-8",
    )
    return out


def default_report_path(project_id: str, run_id: str) -> Path:
    """Default report path under .forge_state/reports/."""
    return Path(".forge_state") / "reports" / f"{project_id}_{run_id}.md"
