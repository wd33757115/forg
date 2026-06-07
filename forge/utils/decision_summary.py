"""Five-bullet decision summary for Demo and Run Report (C2)."""

from __future__ import annotations

from typing import Any


def build_decision_summary_bullets(
    result: dict[str, Any],
    *,
    stats: dict[str, Any] | None = None,
) -> list[str]:
    """
    Return ≤5 narrative bullets: 判型 → 方案 → 合规 → 半自治 → 结果.

    Used at the top of Rich Demo and Markdown reports.
    """
    if stats is None:
        from forge.cli.stats import compute_run_stats

        stats = compute_run_stats(result, elapsed_ms=result.get("_elapsed_ms"))

    solution = result.get("last_solution") or {}
    compliance = result.get("last_compliance_result") or {}
    ptype = solution.get("problem_type") or stats.get("problem_type", "—")
    rec = solution.get("recommended_solution_id", "—")
    refs = solution.get("rule_pack_references") or []
    ref_preview = ", ".join(
        f"`{r.get('rule_id', '?')}`" for r in refs[:3] if isinstance(r, dict)
    )

    conflict = result.get("classification_conflict")
    type_note = f"类型 **{ptype}**"
    if conflict:
        type_note += (
            f"（CLI={conflict.get('hinted_type')}，自动={conflict.get('auto_type')}）"
        )

    bullets: list[str] = [
        f"**判型与调查** — {type_note}"
        + (f"；引用 {ref_preview}" if ref_preview else ""),
        f"**推荐方案** — `{rec}`"
        + (
            f"（方案置信度 {float(solution['confidence']):.0%}）"
            if solution.get("confidence") is not None
            else ""
        ),
        f"**合规闭环** — {compliance.get('compliance_status', '—')}"
        f" / 模式 {compliance.get('check_mode', 'advisory')}"
        f" / failed={len(compliance.get('failed_items') or [])}"
        + (
            f" / 重试 {stats.get('compliance_retries', 0)} 次"
            if stats.get("compliance_retries")
            else ""
        ),
        f"**半自治** — 会话置信度 {stats.get('confidence_score', 0):.0%}"
        f" → {result.get('confidence_recommendation', '—')}"
        f"；审批 **{result.get('approval_status', '—')}**"
        f"；执行 {len(result.get('execution_tasks') or [])} 项",
        f"**交付** — 资料 {stats.get('documents_generated', 0)} 份"
        f"；耗时 {stats.get('elapsed_s', '—')}s"
        f"；风险 {stats.get('risk_level', '—')}",
    ]
    return bullets[:5]


def format_decision_summary_markdown(result: dict[str, Any], *, stats: dict[str, Any] | None = None) -> str:
    """Markdown section body for reports."""
    lines = ["## 决策摘要", ""]
    for i, bullet in enumerate(build_decision_summary_bullets(result, stats=stats), 1):
        lines.append(f"{i}. {bullet}")
    lines.append("")
    return "\n".join(lines)
