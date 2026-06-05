"""Singleton RulePackLoader — load and cache Rule Pack bundles."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from forge.core.rule_pack import (
    DEFAULT_PACK_FILE,
    DEFAULT_RULE_PACKS_DIR,
    RuleModule,
    RulePack,
)

# Backward-compatible alias: per-module dict keyed by module_id
ModuleMap = dict[str, RuleModule]


class RulePackLoader:
    """
    Thread-safe singleton loader with in-memory cache.

    Usage:
        loader = RulePackLoader.get_instance()
        pack = loader.load("system_integration_v1.json")
    """

    _instance: RulePackLoader | None = None
    _lock: Lock = Lock()

    def __init__(self, packs_dir: Path | None = None) -> None:
        self.packs_dir = packs_dir or DEFAULT_RULE_PACKS_DIR
        self._cache: dict[str, RulePack] = {}

    @classmethod
    def get_instance(cls, packs_dir: Path | None = None) -> RulePackLoader:
        """Return the global singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(packs_dir)
        elif packs_dir is not None and cls._instance.packs_dir != packs_dir:
            cls._instance.packs_dir = packs_dir
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Clear singleton (useful in tests)."""
        with cls._lock:
            cls._instance = None

    def _resolve_path(self, path: str) -> Path:
        file_path = Path(path)
        if file_path.is_absolute():
            return file_path
        return self.packs_dir / file_path.name if (self.packs_dir / file_path.name).exists() else file_path

    def load(self, path: str = DEFAULT_PACK_FILE, *, use_cache: bool = True) -> RulePack:
        """
        Load a Rule Pack from path (relative to packs_dir or absolute).

        Results are cached by resolved absolute path.
        """
        resolved = str(self._resolve_path(path).resolve())
        if use_cache and resolved in self._cache:
            return self._cache[resolved]

        pack = RulePack.load_rule_pack(resolved)
        if use_cache:
            self._cache[resolved] = pack
        return pack

    def load_default(self) -> RulePack:
        """Load the default system integration Rule Pack."""
        return self.load(DEFAULT_PACK_FILE)

    def list_available(self) -> list[str]:
        """List JSON Rule Pack files in packs_dir."""
        if not self.packs_dir.exists():
            return []
        return sorted(p.name for p in self.packs_dir.glob("*.json"))

    def get_modules(
        self,
        path: str = DEFAULT_PACK_FILE,
        module_names: list[str] | None = None,
    ) -> ModuleMap:
        """
        Load a pack and return enabled modules as a dict.

        Optionally filter to a subset of module_names.
        """
        pack = self.load(path)
        enabled = pack.get_enabled_module_map()
        if module_names is None:
            return enabled
        return {name: enabled[name] for name in module_names if name in enabled}


def get_rule_pack(
    modules: tuple[str, ...] | None = None,
    pack_path: str = DEFAULT_PACK_FILE,
) -> ModuleMap:
    """
    Convenience function: load default (or specified) pack and return module map.

    Maintains backward compatibility with agents/tools expecting dict[str, RuleModule].
    """
    loader = RulePackLoader.get_instance()
    module_list = list(modules) if modules else None
    return loader.get_modules(pack_path, module_list)
