"""Enrich Rule Pack rules with public standard citations (no copyrighted full text)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from forge.core.rule_pack import PROJECT_ROOT

logger = logging.getLogger(__name__)

DEFAULT_CATALOG = PROJECT_ROOT / "rule_packs" / "standards_public_catalog.json"
DEFAULT_PACK = PROJECT_ROOT / "rule_packs" / "system_integration_v1.json"


def load_catalog(path: Path | str | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path else DEFAULT_CATALOG
    with catalog_path.open(encoding="utf-8") as f:
        return json.load(f)


def _merge_references(existing: list[str], new_items: list[str]) -> list[str]:
    seen = {item.strip() for item in existing}
    merged = list(existing)
    for item in new_items:
        text = item.strip()
        if text and text not in seen:
            seen.add(text)
            merged.append(text)
    return merged


def enrich_rule_pack_dict(
    pack_data: dict[str, Any],
    catalog: dict[str, Any],
    *,
    overwrite_description: bool = False,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Merge catalog citations into pack JSON dict. Returns (pack, stats)."""
    rule_catalog = catalog.get("rules", {})
    stats = {"rules_enriched": 0, "citations_added": 0, "rules_skipped": 0}

    for _mod_id, module in (pack_data.get("modules") or {}).items():
        for rule in module.get("rules") or []:
            rid = rule.get("id", "")
            entry = rule_catalog.get(rid)
            if not entry:
                stats["rules_skipped"] += 1
                continue

            citations = entry.get("citations") or []
            before = len(rule.get("references") or [])
            rule["references"] = _merge_references(rule.get("references") or [], citations)
            added = len(rule["references"]) - before
            if added > 0:
                stats["rules_enriched"] += 1
                stats["citations_added"] += added

            summary = (entry.get("public_summary") or "").strip()
            if summary and overwrite_description and not rule.get("description"):
                rule["description"] = summary

    return pack_data, stats


def enrich_rule_pack_file(
    pack_path: Path | str | None = None,
    catalog_path: Path | str | None = None,
    *,
    dry_run: bool = False,
    bump_version: bool = True,
) -> dict[str, Any]:
    """Load pack JSON, enrich references from catalog, optionally write back."""
    pack_file = Path(pack_path) if pack_path else DEFAULT_PACK
    catalog = load_catalog(catalog_path)

    with pack_file.open(encoding="utf-8") as f:
        pack_data = json.load(f)

    enriched, stats = enrich_rule_pack_dict(pack_data, catalog)
    if bump_version and not dry_run:
        version = enriched.get("version", "1.0.0")
        if version.startswith("1.1"):
            enriched["version"] = "1.2.0"
        enriched["description"] = (
            (enriched.get("description") or "")
            + "；references 已对齐公开标准目录（等保2.0/ITIL4/ISO20000）"
        ).strip("；")

    result = {"pack": str(pack_file), "catalog": str(catalog_path or DEFAULT_CATALOG), **stats}
    if dry_run:
        result["dry_run"] = True
        return result

    with pack_file.open("w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
        f.write("\n")

    logger.info(
        "Enriched %s | rules=%d citations_added=%d",
        pack_file.name,
        stats["rules_enriched"],
        stats["citations_added"],
    )
    return result
