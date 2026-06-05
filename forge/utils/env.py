"""Load environment variables from .env if present."""

from __future__ import annotations

import os
from pathlib import Path


def _manual_load(env_path: Path) -> None:
    """Minimal .env parser (fallback when python-dotenv is unavailable)."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_dotenv() -> None:
    """
    Load ``.env`` from cwd or project root.

    Uses ``python-dotenv`` when installed; otherwise falls back to a minimal parser.
    """
    try:
        from dotenv import load_dotenv as _dotenv_load

        _dotenv_load()
        return
    except ImportError:
        pass

    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    _manual_load(env_path)
