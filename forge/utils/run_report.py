"""Backward-compatible re-exports — prefer ``forge.utils.report``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.utils.report import (
    default_report_path as _default_report_path,
    generate_run_report,
    save_run_report,
)


def build_run_report_markdown(
    result: dict[str, Any],
    *,
    question: str = "",
    scenario: str = "",
    elapsed_ms: float = 0.0,
) -> str:
    return generate_run_report(
        result,
        question=question,
        scenario=scenario,
        elapsed_ms=elapsed_ms,
    )


def write_run_report(
    result: dict[str, Any],
    path: str | Path,
    *,
    question: str = "",
    scenario: str = "",
    elapsed_ms: float = 0.0,
) -> Path:
    return save_run_report(
        result,
        path,
        question=question,
        scenario=scenario,
        elapsed_ms=elapsed_ms,
    )


def default_report_path(project_id: str, run_id: str) -> Path:
    """Legacy path under ``.forge_state/reports/`` when project_id is known."""
    _ = project_id
    return Path(".forge_state") / "reports" / f"{project_id}_{run_id}.md"


# Also expose reports/ path helper
def default_public_report_path(state: dict[str, Any]) -> Path:
    return _default_report_path(state)
