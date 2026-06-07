"""Build human-readable compliance check explanations (rule traceability)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from forge.agents.compliance_output import ComplianceOutput

_RULE_PREFIXES = ("db-", "itil-", "si-")


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


def _canonical_rule_id(item: dict[str, Any]) -> str:
    rid = str(item.get("rule_id") or item.get("check_id") or "")
    if any(rid.startswith(p) for p in _RULE_PREFIXES):
        return rid
    ref = str(item.get("rule_reference") or "").split(",")[0].strip()
    if any(ref.startswith(p) for p in _RULE_PREFIXES):
        return ref
    return rid


def _severity_for_item(item: dict[str, Any]) -> str:
    status = item.get("status", "")
    category = str(item.get("category", ""))
    if status == "warning":
        return "low"
    if "dengbao" in category and status == "fail":
        return "high"
    if status == "fail":
        return "medium"
    return "low"


def _item_in_failed_set(item: dict[str, Any], check_mode: str) -> bool:
    """Filter check items into failed_items per check_mode (strict / advisory / lenient)."""
    status = item.get("status", "")
    category = str(item.get("category", ""))
    if status == "fail":
        if check_mode == "lenient":
            return "dengbao" in category or bool(_canonical_rule_id(item))
        return True
    if status == "warning" and check_mode == "strict":
        return True
    return False


def build_compliance_explainability(
    output: "ComplianceOutput",
    *,
    check_mode: str = "advisory",
) -> dict[str, Any]:
    """
    Derive matched_rules, failed_items, suggestions from ComplianceOutput.

    Used to enrich structured persistence and CLI/report display.
    """
    from forge.agents.compliance_output import FailedCheckItem

    matched: set[str] = set()
    failed: list[FailedCheckItem] = []

    for mod in output.results:
        for item in mod.items:
            raw = item.model_dump()
            rid = _canonical_rule_id(raw)
            if rid:
                matched.add(rid)
            if _item_in_failed_set(raw, check_mode):
                failed.append(
                    FailedCheckItem(
                        rule_id=rid or item.check_id,
                        module=mod.module,
                        title=item.title,
                        description=item.detail or item.title,
                        status=item.status,
                        severity=_severity_for_item(raw),
                    )
                )

    suggestions = list(output.recommendations or [])
    if not suggestions and failed:
        suggestions = [
            f"对照 `{f.rule_id}` 整改：{f.title} — {f.description[:80]}"
            for f in failed[:8]
            if f.rule_id
        ]
    if check_mode == "lenient" and output.missing_items:
        suggestions = suggestions or [
            f"[lenient] 记录缺口（非阻断）：{m[:100]}" for m in output.missing_items[:5]
        ]

    return {
        "matched_rules": sorted(matched),
        "failed_items": failed,
        "suggestions": suggestions,
    }


def enrich_compliance_output(
    output: "ComplianceOutput",
    *,
    check_mode: str = "advisory",
) -> "ComplianceOutput":
    """Return ComplianceOutput with explainability fields populated."""
    extra = build_compliance_explainability(output, check_mode=check_mode)
    return output.model_copy(update=extra)
