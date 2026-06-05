"""Simple JSON persistence for Forge ProjectState."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import messages_from_dict, messages_to_dict

from forge.core.state import ProjectState, create_initial_state

DEFAULT_STATE_DIR = Path(".forge_state")


def _serialize_state(state: ProjectState | dict[str, Any]) -> dict[str, Any]:
    """Convert ProjectState to a JSON-serializable dict."""
    data = dict(state)
    messages = data.get("messages", [])
    if messages:
        data["messages"] = messages_to_dict(messages)
    return data


def _deserialize_state(data: dict[str, Any]) -> ProjectState:
    """Restore ProjectState from a serialized dict."""
    restored = dict(data)
    raw_messages = restored.get("messages", [])
    if raw_messages and isinstance(raw_messages[0], dict):
        restored["messages"] = messages_from_dict(raw_messages)
    return ProjectState(**restored)


def save_state(state: ProjectState, path: str | Path) -> Path:
    """
    Save ProjectState to a JSON file.

    Creates parent directories as needed. Returns the resolved file path.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "state": _serialize_state(state),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target.resolve()


def load_state(path: str | Path) -> ProjectState:
    """Load ProjectState from a JSON file saved by `save_state`."""
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"State file not found: {target}")

    payload = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "state" in payload:
        return _deserialize_state(payload["state"])
    return _deserialize_state(payload)


def default_state_path(project_id: str, *, base_dir: str | Path | None = None) -> Path:
    """Default path: `.forge_state/{project_id}.json`."""
    root = Path(base_dir) if base_dir else DEFAULT_STATE_DIR
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_id)
    return root / f"{safe_id}.json"


def save_state_default(state: ProjectState, *, base_dir: str | Path | None = None) -> Path:
    """Save state using the default path for the project's ID."""
    project_id = state.get("project_id", "forge-session")
    return save_state(state, default_state_path(project_id, base_dir=base_dir))


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
