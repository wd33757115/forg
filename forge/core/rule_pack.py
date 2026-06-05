"""Rule Pack models — structured industry rules as executable knowledge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Project root: forge/core/rule_pack.py -> forge -> <root>
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RULE_PACKS_DIR = PROJECT_ROOT / "rule_packs"
DEFAULT_PACK_FILE = "system_integration_v1.json"

KNOWN_MODULES = frozenset({"base_si", "dengbao_2.0", "itil_iso20000"})


class Rule(BaseModel):
    """A single executable rule within a module."""

    id: str
    title: str
    description: str
    category: str
    severity: str = "medium"
    checks: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class RuleModule(BaseModel):
    """One industry/standard module (e.g. base_si, dengbao_2.0)."""

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

    def rule_count(self) -> int:
        return len(self.rules)


class RulePack(BaseModel):
    """
    A bundled Rule Pack containing multiple modules.

    Loaded from a single JSON file (e.g. rule_packs/system_integration_v1.json).
    """

    pack_id: str
    name: str
    version: str
    description: str = ""
    enabled_modules: list[str] = Field(default_factory=list)
    modules: dict[str, RuleModule] = Field(default_factory=dict)

    @field_validator("enabled_modules")
    @classmethod
    def _validate_enabled_module_names(cls, modules: list[str]) -> list[str]:
        for name in modules:
            if name not in KNOWN_MODULES:
                raise ValueError(f"Unknown module in enabled_modules: {name}")
        return modules

    @classmethod
    def load_rule_pack(cls, path: str) -> RulePack:
        """Load a Rule Pack bundle from a JSON file path."""
        file_path = Path(path)
        if not file_path.is_absolute():
            # Resolve relative to project rule_packs/ dir first, then cwd
            candidate = DEFAULT_RULE_PACKS_DIR / file_path
            if candidate.exists():
                file_path = candidate
            elif not file_path.exists():
                file_path = Path.cwd() / path

        if not file_path.exists():
            raise FileNotFoundError(f"Rule Pack file not found: {path}")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def get_module(self, module_name: str) -> RuleModule | None:
        """Return a module by name, or None if not present."""
        return self.modules.get(module_name)

    def get_enabled_modules(self) -> list[str]:
        """Return the list of enabled module names for this pack."""
        return list(self.enabled_modules)

    def validate_module(self, module_name: str) -> bool:
        """
        Check whether a module is enabled, present, and has at least one rule.

        A valid module must be listed in enabled_modules and exist in modules
        with a non-empty rules list.
        """
        if module_name not in self.enabled_modules:
            return False
        module = self.modules.get(module_name)
        if module is None:
            return False
        return module.rule_count() > 0

    def get_enabled_module_map(self) -> dict[str, RuleModule]:
        """Return only enabled modules that pass validation."""
        return {
            name: module
            for name in self.get_enabled_modules()
            if (module := self.get_module(name)) is not None and self.validate_module(name)
        }

    def total_rule_count(self) -> int:
        return sum(m.rule_count() for m in self.get_enabled_module_map().values())

    def to_state_dict(self) -> dict[str, Any]:
        """Serialize for ProjectState.rule_pack field."""
        return self.model_dump()


def merge_rules(modules: dict[str, RuleModule], category: str | None = None) -> list[Rule]:
    """Flatten rules from multiple modules, optionally filtered by category."""
    result: list[Rule] = []
    for module in modules.values():
        if category:
            result.extend(module.rules_by_category(category))
        else:
            result.extend(module.rules)
    return result
