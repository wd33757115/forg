"""Rule Pack loader — structured industry rules as executable knowledge."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Default location: forge/rule_packs/
RULE_PACKS_DIR = Path(__file__).resolve().parent.parent / "rule_packs"

AVAILABLE_MODULES = ("base_si", "dengbao_2.0", "itil_iso20000")


class Rule(BaseModel):
    """A single executable rule within a Rule Pack."""

    id: str
    title: str
    description: str
    category: str
    severity: str = "medium"
    checks: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class RulePack(BaseModel):
    """A collection of rules for one industry/standard module."""

    module_id: str
    name: str
    version: str
    description: str = ""
    rules: list[Rule] = Field(default_factory=list)

    def get_rule(self, rule_id: str) -> Rule | None:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def rules_by_category(self, category: str) -> list[Rule]:
        return [r for r in self.rules if r.category == category]


class RulePackLoader:
    """Loads Rule Pack definitions from JSON files on disk."""

    def __init__(self, packs_dir: Path | None = None) -> None:
        self.packs_dir = packs_dir or RULE_PACKS_DIR

    def load_module(self, module_id: str) -> RulePack:
        path = self.packs_dir / f"{module_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Rule Pack not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return RulePack.model_validate(data)

    def load_modules(self, module_ids: list[str]) -> dict[str, RulePack]:
        return {mid: self.load_module(mid) for mid in module_ids}

    def list_available(self) -> list[str]:
        return sorted(p.stem for p in self.packs_dir.glob("*.json"))


@lru_cache(maxsize=1)
def get_rule_pack(
    modules: tuple[str, ...] = AVAILABLE_MODULES,
    packs_dir: str | None = None,
) -> dict[str, RulePack]:
    """
    Load and cache Rule Packs for the given modules.

    Returns a dict keyed by module_id.
    """
    loader = RulePackLoader(Path(packs_dir) if packs_dir else None)
    return loader.load_modules(list(modules))


def merge_rules(packs: dict[str, RulePack], category: str | None = None) -> list[Rule]:
    """Flatten rules from multiple packs, optionally filtered by category."""
    result: list[Rule] = []
    for pack in packs.values():
        if category:
            result.extend(pack.rules_by_category(category))
        else:
            result.extend(pack.rules)
    return result
