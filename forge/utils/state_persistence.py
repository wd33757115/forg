"""JSON persistence for Forge ProjectState — save, load, resume."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, messages_from_dict, messages_to_dict

from forge.core.state import ProjectState, create_initial_state

DEFAULT_STATE_DIR = Path(".forge_state")
STATE_FORMAT_VERSION = 2

# Fields reset when starting a new workflow run on top of saved state
_RUN_RESET_FIELDS: dict[str, Any] = {
    "compliance_retry_count": 0,
    "last_solution": None,
    "last_compliance_result": None,
    "generated_documents": [],
    "last_pm_advice": None,
    "last_security_result": None,
    "last_operations_result": None,
    "specialist_queue": [],
    "specialists_completed": [],
    "final_output": None,
    "active_workflow": None,
    "workflow_step": None,
    "next_agent": None,
    "workflow_plan": None,
    "pipeline_trace": [],
    "agent_errors": [],
    "execution_tasks": [],
    "execution_results": [],
    "approval_requests": [],
    "pending_approvals": [],
    "approval_status": None,
    "confidence_level": None,
    "confidence_recommendation": None,
    "last_confidence_result": None,
    "memory_graph": None,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_state(state: ProjectState | dict[str, Any]) -> dict[str, Any]:
    """Convert ProjectState to a JSON-serializable dict."""
    data = dict(state)
    messages = data.get("messages", [])
    if messages and not isinstance(messages[0], dict):
        data["messages"] = messages_to_dict(messages)
    return data


def _default_fields() -> dict[str, Any]:
    """Default values for fields that may be missing in older saves."""
    base = create_initial_state("_template_")
    return dict(base)


def _deserialize_state(data: dict[str, Any]) -> ProjectState:
    """Restore ProjectState from a serialized dict (backward compatible)."""
    restored = {**_default_fields(), **dict(data)}
    # Remove template project_id if merged from defaults
    if restored.get("project_id") == "_template_" and "project_id" in data:
        restored["project_id"] = data["project_id"]

    raw_messages = restored.get("messages", [])
    if raw_messages and isinstance(raw_messages[0], dict):
        restored["messages"] = messages_from_dict(raw_messages)

    # Ensure lists exist
    for key in (
        "specialist_queue",
        "specialists_completed",
        "pipeline_trace",
        "agent_errors",
        "conversation_history",
        "knowledge_base",
    ):
        if restored.get(key) is None:
            restored[key] = []

    return ProjectState(**{k: restored[k] for k in ProjectState.__annotations__})


def save_state(
    state: ProjectState,
    path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """
    Save ProjectState to a JSON file (format v2).

    ``metadata`` may include last_question, scenario, etc.
  """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    meta = {
        "saved_at": _utc_now(),
        "project_id": state.get("project_id"),
        "format_version": STATE_FORMAT_VERSION,
        **(metadata or {}),
    }

    payload = {
        "version": STATE_FORMAT_VERSION,
        "metadata": meta,
        "state": _serialize_state(state),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target.resolve()


def load_state(path: str | Path) -> ProjectState:
    """Load ProjectState from a JSON file (v1 or v2)."""
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"State file not found: {target}")

    payload = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "state" in payload:
        return _deserialize_state(payload["state"])
    return _deserialize_state(payload)


def load_state_with_metadata(path: str | Path) -> tuple[ProjectState, dict[str, Any]]:
    """Load state and envelope metadata."""
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "state" in payload:
        return _deserialize_state(payload["state"]), payload.get("metadata", {})
    return _deserialize_state(payload), {}


def default_state_path(project_id: str, *, base_dir: str | Path | None = None) -> Path:
    """Default path: `.forge_state/{project_id}.json`."""
    root = Path(base_dir) if base_dir else DEFAULT_STATE_DIR
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_id)
    return root / f"{safe_id}.json"


def save_state_default(
    state: ProjectState,
    *,
    base_dir: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Save state using the default path for the project's ID."""
    project_id = state.get("project_id", "forge-session")
    return save_state(state, default_state_path(project_id, base_dir=base_dir), metadata=metadata)


def list_saved_states(*, base_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """List JSON state files under the default directory."""
    root = Path(base_dir) if base_dir else DEFAULT_STATE_DIR
    if not root.exists():
        return []

    results: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            _, meta = load_state_with_metadata(path)
            results.append(
                {
                    "path": str(path.resolve()),
                    "project_id": meta.get("project_id", path.stem),
                    "saved_at": meta.get("saved_at"),
                    "last_question": meta.get("last_question"),
                }
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            results.append({"path": str(path.resolve()), "project_id": path.stem, "error": True})
    return results


def prepare_state_for_run(
    state: ProjectState,
    question: str,
    *,
    protection_level: str | None = None,
    reset_outputs: bool = True,
) -> ProjectState:
    """
    Prepare a loaded (or fresh) state for a new workflow invocation.

    Preserves knowledge_base, documents, wbs; resets per-run outputs when requested.
    """
    prepared = dict(state)

    if reset_outputs:
        for key, value in _RUN_RESET_FIELDS.items():
            prepared[key] = value if not isinstance(value, list) else list(value)

    prepared["run_id"] = str(uuid4())[:8]
    prepared["messages"] = list(prepared.get("messages", [])) + [HumanMessage(content=question)]

    rule_pack = dict(prepared.get("rule_pack") or {})
    if protection_level:
        rule_pack["protection_level"] = protection_level
    if not rule_pack.get("pack_id"):
        rule_pack["pack_id"] = "system_integration_v1"
    prepared["rule_pack"] = rule_pack

    return ProjectState(**{k: prepared[k] for k in ProjectState.__annotations__})


def load_state_or_create(
    path: str | Path,
    *,
    project_id: str = "forge-session",
) -> ProjectState:
    """Load state from file, or return a fresh initial state if missing."""
    try:
        return load_state(path)
    except FileNotFoundError:
        return create_initial_state(project_id)
