"""Load environment variables from .env if present."""

from __future__ import annotations

from pathlib import Path


def load_dotenv() -> None:
    """Minimal .env loader (no extra dependency)."""
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        # Also check project root relative to this package
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in __import__("os").environ:
            __import__("os").environ[key] = value
