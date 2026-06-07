"""Extract Rule Pack rule_id references from agent research text."""

from __future__ import annotations

import re

# Canonical Forge rule_id patterns (db-*, itil-*, si-*)
_RULE_ID_PATTERN = re.compile(r"\b((?:db|itil|si)-[a-z0-9-]+)\b", re.IGNORECASE)


def extract_rule_ids_from_text(text: str, *, limit: int = 12) -> list[str]:
    """Return unique rule_ids mentioned in free text (preserves first-seen order)."""
    if not text:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _RULE_ID_PATTERN.finditer(text):
        rid = match.group(1).lower()
        if rid not in seen:
            seen.add(rid)
            ordered.append(rid)
        if len(ordered) >= limit:
            break
    return ordered
