"""Build human-readable compliance check explanations (rule traceability)."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from forge.agents.compliance_output import ComplianceOutput, FailedCheckItem

_RULE_PREFIXES = ("db-", "itil-", "si-")


@lru_cache(maxsize=1)
def _rule_severity_index() -> dict[str, str]:
    """Load Rule Pack rule_id → severity (critical/high/medium/low)."""
    from forge.core.rule_pack import DEFAULT_PACK_FILE, RulePack

    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    index: dict[str, str] = {}
    for module in pack.modules.values():
        for rule in module.rules:
            index[rule.id] = rule.severity
    return index


def build_check_explanations(compliance: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Flatten module check items into explainable records with rule_id linkage.

    Each record includes severity and suggestion (B1).
    """
    explanations: list[dict[str, Any]] = []
    for mod in compliance.get("results") or []:
        module_id = mod.get("module", "?")
        for item in mod.get("items") or []:
            rid = _canonical_rule_id(item)
            status = item.get("status", "?")
            title = item.get("title", "")
            detail = item.get("detail", "")
            severity = _severity_for_item(item)
            suggestion = ""
            if status in ("fail", "warning"):
                suggestion = _suggestion_for_item(item, severity)
            explanations.append(
                {
                    "module": module_id,
                    "rule_id": rid,
                    "status": status,
                    "title": title,
                    "severity": severity,
                    "suggestion": suggestion,
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
    """Map check item to severity; prefer Rule Pack definition (B1)."""
    rid = _canonical_rule_id(item)
    if rid:
        pack_sev = _rule_severity_index().get(rid)
        if pack_sev in ("critical", "high", "medium", "low"):
            return pack_sev

    status = item.get("status", "")
    category = str(item.get("category", ""))
    if status == "warning":
        return "low"
    if "dengbao" in category and status == "fail":
        return "high"
    if status == "fail":
        return "medium"
    return "low"


def _suggestion_for_item(item: dict[str, Any], severity: str) -> str:
    rid = _canonical_rule_id(item)
    title = item.get("title", "") or "检查项"
    detail = (item.get("detail") or "")[:120]
    if rid:
        return (
            f"对照 `{rid}` 补齐证据或整改（severity={severity}）：{title}"
            + (f" — {detail}" if detail else "")
        )
    return f"整改 {title}（severity={severity}）" + (f" — {detail}" if detail else "")


def _item_in_failed_set(item: dict[str, Any], check_mode: str) -> bool:
    """
    Filter check items into failed_items per check_mode (B2).

    - strict: fail + warning → failed_items
    - advisory: fail only (warning 记入 check_explanations)
    - lenient: fail 且 severity 为 high/critical
    """
    status = item.get("status", "")
    if status not in ("fail", "warning"):
        return False

    if check_mode == "strict":
        return True

    if check_mode == "advisory":
        return status == "fail"

    if check_mode == "lenient":
        if status == "warning":
            return False
        return _severity_for_item(item) in ("high", "critical")

    return status == "fail"


def resolve_compliance_status_from_output(
    output: "ComplianceOutput",
    *,
    check_mode: str = "advisory",
) -> str:
    """
    Derive compliant | partial | non_compliant from enriched failed_items (B2).

    Aligns displayed status with check_mode filtering, not only raw fail counts.
    """
    failed = output.failed_items or []
    if not failed:
        return "compliant"

    if check_mode == "strict":
        return "non_compliant"

    if check_mode == "lenient":
        blocking = [f for f in failed if f.severity in ("high", "critical")]
        return "non_compliant" if blocking else "partial"

    # advisory
    if all(f.severity in ("low", "medium") for f in failed):
        return "partial"
    return "non_compliant"


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
                severity = _severity_for_item(raw)
                failed.append(
                    FailedCheckItem(
                        rule_id=rid or item.check_id,
                        module=mod.module,
                        title=item.title,
                        description=item.detail or item.title,
                        status=item.status,
                        severity=severity,
                        suggestion=_suggestion_for_item(raw, severity),
                    )
                )

    suggestions = list(output.recommendations or [])
    if not suggestions and failed:
        suggestions = [f.suggestion for f in failed[:8] if f.suggestion]
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


def summarize_mode_comparison(
    *,
    strict: "ComplianceOutput",
    advisory: "ComplianceOutput",
    lenient: "ComplianceOutput",
) -> dict[str, Any]:
    """Summary payload for compliance_mode_diff script (B3)."""
    modes = {"strict": strict, "advisory": advisory, "lenient": lenient}
    rows = {}
    for name, out in modes.items():
        rows[name] = {
            "failed_count": len(out.failed_items),
            "matched_count": len(out.matched_rules),
            "compliance_status": resolve_compliance_status_from_output(out, check_mode=name),
            "failed_rule_ids": [f.rule_id for f in out.failed_items[:12]],
        }
    return rows
