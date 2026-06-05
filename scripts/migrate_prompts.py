"""One-off: move *_prompt.py content into prompts/<agent>/prompts.py (legacy re-exports)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "forge" / "prompts"

PAIRS = [
    ("problem_solver_prompt.py", "problem_solver"),
    ("compliance_prompt.py", "compliance"),
    ("security_prompt.py", "security"),
    ("operations_prompt.py", "operations"),
    ("document_prompt.py", "document"),
    ("pm_advisor_prompt.py", "pm_advisor"),
]


def _export_names(content: str) -> list[str]:
    names: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith('"""'):
            continue
        if stripped.startswith("from "):
            continue
        if "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        if name.isidentifier() and name.isupper():
            names.append(name)
    return names


def main() -> None:
    for legacy_name, module in PAIRS:
        src = ROOT / legacy_name
        dst = ROOT / module / "prompts.py"
        content = src.read_text(encoding="utf-8")
        if content.lstrip().startswith('"""Legacy import path'):
            print(f"skip {legacy_name} (already legacy shim)")
            continue
        dst.write_text(content, encoding="utf-8")
        exports = _export_names(content)
        exp_block = ",\n    ".join(exports)
        all_block = ",\n    ".join(f'"{e}"' for e in exports)
        shim = (
            f'"""Legacy import path — canonical content in ``{module}/prompts.py``."""\n\n'
            f"from forge.prompts.{module}.prompts import (\n"
            f"    {exp_block},\n"
            f")\n\n"
            f"__all__ = [\n"
            f"    {all_block},\n"
            f"]\n"
        )
        src.write_text(shim, encoding="utf-8")
        print(f"migrated {legacy_name} -> {module}/prompts.py ({len(exports)} symbols)")


if __name__ == "__main__":
    main()
