"""Forge logging utilities."""

from __future__ import annotations

import logging
import os
import sys
from typing import Literal

_LOG_FORMAT = "%(asctime)s │ %(name)-18s │ %(levelname)-7s │ %(message)s"
_DATE_FORMAT = "%H:%M:%S"
_configured = False

Level = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


def setup_logging(level: Level = "INFO", *, log_file: str | None = None) -> None:
    """Configure root Forge logging once per process."""
    global _configured
    if _configured:
        return

    root = logging.getLogger("forge")
    root.setLevel(getattr(logging, level))
    root.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    _configured = True


def log_pipeline_step(
    logger: logging.Logger,
    *,
    run_id: str,
    step: str,
    detail: str = "",
    level: Level = "INFO",
) -> None:
    """Emit a structured pipeline step log for agent call-chain tracing."""
    msg = f"[{run_id}] {step}"
    if detail:
        msg = f"{msg} | {detail}"
    logger.log(getattr(logging, level), msg)


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger under the ``forge`` namespace.

    Example: get_logger("supervisor") → forge.supervisor
    """
    if not _configured:
        env_level = os.environ.get("FORGE_LOG_LEVEL", "INFO").upper()
        setup_logging(env_level if env_level in ("DEBUG", "INFO", "WARNING", "ERROR") else "INFO")
    return logging.getLogger(f"forge.{name}")
