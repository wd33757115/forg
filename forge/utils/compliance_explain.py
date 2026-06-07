"""Build human-readable compliance check explanations (rule traceability)."""

from __future__ import annotations

from typing import Any


def build_check_explanations(compliance: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Flatten module check items into explainable records with rule_id linkage.

    Used in Compliance structured output and run reports.
    """
    explanations: list[dict[str, Any]] = []
    for mod in compliance.get("results") or []:
        module_id = mod.get("module", "?")
        for item in mod.get("items") or []:
            rid = item.get("rule_id") or item.get("check_id") or ""
            status = item.get("status", "?")
            title = item.get("title", "")
            detail = item.get("detail", "")
            explanations.append(
                {
                    "module": module_id,
                    "rule_id": rid,
                    "status": status,
                    "title": title,
                    "explanation": _format_explanation(rid, title, status, detail),
                }
            )
    return explanations


def _format_explanation(rule_id: str, title: str, status: str, detail: str) -> str:
    prefix = f"[{status.upper()}]"
    rule_part = f" rule_id={rule_id}" if rule_id else ""
    body = detail or title
    return f"{prefix} {title}{rule_part}: {body}".strip()
