"""Export pipeline trace and conversation history for --verbose / --export-trace (C3)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_trace_export_payload(result: dict[str, Any], *, question: str = "") -> dict[str, Any]:
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "run_id": result.get("run_id"),
        "project_id": result.get("project_id"),
        "question": question[:2000] if question else None,
        "pipeline_trace": result.get("pipeline_trace") or [],
        "conversation_history": result.get("conversation_history") or [],
        "agent_errors": result.get("agent_errors") or [],
        "workflow_plan": result.get("workflow_plan"),
        "reference_provenance": result.get("reference_provenance"),
        "classification_conflict": result.get("classification_conflict"),
    }


def write_trace_export(
    result: dict[str, Any],
    path: str | Path,
    *,
    question: str = "",
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_trace_export_payload(result, question=question)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
