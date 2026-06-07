"""Structured compliance retry feedback for ProblemSolver (P0)."""

from __future__ import annotations

from typing import Any


def build_compliance_feedback(
    compliance: dict[str, Any],
    *,
    retry_count: int = 0,
) -> dict[str, Any]:
    """Build machine-readable feedback from last_compliance_result."""
    failed = compliance.get("failed_items") or []
    suggestions = compliance.get("suggestions") or compliance.get("recommendations") or []
    return {
        "retry_count": retry_count,
        "compliance_status": compliance.get("compliance_status")
        or compliance.get("overall_status"),
        "check_mode": compliance.get("check_mode"),
        "risk_level": compliance.get("risk_level"),
        "failed_items": [
            {
                "rule_id": item.get("rule_id", ""),
                "severity": item.get("severity", "medium"),
                "status": item.get("status", "fail"),
                "title": item.get("title", ""),
                "suggestion": item.get("suggestion", ""),
                "module": item.get("module", ""),
            }
            for item in failed[:12]
        ],
        "missing_items": list(compliance.get("missing_items") or [])[:8],
        "suggestions": list(suggestions)[:8],
        "failed_rule_ids": [item.get("rule_id") for item in failed if item.get("rule_id")][:12],
    }


def format_compliance_feedback_for_prompt(feedback: dict[str, Any] | None) -> str:
    """Markdown block injected into ProblemSolver ReAct / structured prompts."""
    if not feedback:
        return "（无 — 首次生成方案，无需响应历史合规失败项）"

    lines = [
        f"**重试轮次**: {feedback.get('retry_count', '?')}",
        f"**合规状态**: {feedback.get('compliance_status', '—')} | "
        f"**模式**: {feedback.get('check_mode', '—')} | "
        f"**风险**: {feedback.get('risk_level', '—')}",
        "",
        "以下 failed_items **必须逐条**在新方案的 rule_pack_references、reasoning、next_actions 中响应：",
    ]
    for item in feedback.get("failed_items") or []:
        rid = item.get("rule_id", "—")
        lines.append(
            f"- `[{item.get('status', 'fail')}]` `{rid}` "
            f"**{item.get('severity', '—')}** {item.get('title', '')}"
        )
        if item.get("suggestion"):
            lines.append(f"  - 整改建议: {item['suggestion'][:200]}")

    missing = feedback.get("missing_items") or []
    if missing:
        lines.extend(["", "**缺口 (missing_items)**:"])
        for m in missing[:6]:
            lines.append(f"- {m}")

    lines.extend(
        [
            "",
            "**输出要求**: reasoning 须说明每条 failed rule_id 如何被新方案覆盖；"
            "不得忽略上述失败项。",
        ]
    )
    return "\n".join(lines)
